from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from app.collectors.sink import connect_redis


def default_data_dir() -> Path:
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    official = Path("/app/data/official-only")
    if official.is_dir():
        return official
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / "data" / "official-only"
        if candidate.is_dir():
            return candidate
    return Path("data/official-only")


class _EvidenceBatch:
    def __init__(self, graph, size: int = 32, interval: float = 1.0):
        self._graph = graph
        self._size = size
        self._interval = interval
        self._next_flush = time.monotonic() + interval
        self._buf: list[dict] = []

    def __call__(self, snapshot: dict) -> None:
        self._buf.append(
            {
                "id": snapshot["id"],
                "path": snapshot["path"],
                "source": snapshot["source"],
                "company": snapshot["company"],
                "observed_at": snapshot.get("observed_at") or "",
                "simhash": snapshot["simhash"],
            }
        )
        if len(self._buf) >= self._size or time.monotonic() >= self._next_flush:
            self.flush()

    def drop(self, evidence_id: str) -> None:
        self._buf = [row for row in self._buf if row["id"] != evidence_id]
        self._graph.delete_evidence_many([evidence_id])

    def flush(self) -> None:
        if not self._buf:
            return
        self._graph.upsert_evidence_many(self._buf)
        self._buf.clear()
        self._next_flush = time.monotonic() + self._interval


def _evidence_writer():
    from app import graph

    graph.init_graph()
    return _EvidenceBatch(graph)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl official career portals into data/official-only/jd")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--redis-url", default=None)
    parser.add_argument("--daily", action="store_true", help="lock, crawl official portals, then extract")
    parser.add_argument("--then-pipeline", action="store_true")
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="write snapshots and Redis events only",
    )
    args = parser.parse_args(argv)

    data_dir = args.data_dir or default_data_dir()
    out_dir = args.out_dir or (data_dir / "jd")
    redis = connect_redis(args.redis_url)
    then_pipeline = args.then_pipeline or args.daily

    on_evidence = None
    if not args.skip_graph:
        try:
            on_evidence = _evidence_writer()
        except Exception as exc:
            print(f"graph skipped: {exc}", file=sys.stderr)

    from app.collectors.ats import CollectLock

    lock = CollectLock(data_dir)
    if not lock.acquire():
        print(json.dumps({"error": "collect already running"}, ensure_ascii=False))
        return 2
    try:
        from app.collectors.ats import run_official
        from app.ops_status import record

        stats = run_official(
            data_dir=data_dir,
            out_dir=out_dir,
            redis=redis,
            on_evidence=on_evidence,
        )
        record("collect", "success" if stats.get("ok") else "failed", portals=stats.get("portals"))
        if on_evidence is not None:
            on_evidence.flush()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        if then_pipeline:
            from app.pipeline.__main__ import main as pipeline_main

            return pipeline_main([])
        return 0 if stats.get("ok", True) else 1
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
