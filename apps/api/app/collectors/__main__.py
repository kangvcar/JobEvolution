from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.collectors.controller import run_ingest
from app.collectors.sink import connect_redis


def default_data_dir() -> Path:
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    candidates: list[Path] = []
    docker = Path("/app/data")
    if docker.is_dir():
        candidates.append(docker)
    cwd = Path.cwd()
    candidates.extend(p / "data" for p in (cwd, *cwd.parents))
    candidates.extend(p / "data" for p in Path(__file__).resolve().parents)
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.csv")):
            return candidate
    return Path("data")


class _EvidenceBatch:
    def __init__(self, graph, size: int = 250):
        self._graph = graph
        self._size = size
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
        if len(self._buf) >= self._size:
            self.flush()

    def flush(self) -> None:
        if not self._buf:
            return
        self._graph.upsert_evidence_many(self._buf)
        self._buf.clear()


def _evidence_writer():
    from app import graph

    graph.init_graph()
    return _EvidenceBatch(graph)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest local JD tables into data/jd")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--redis-url", default=None)
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="write snapshots and Redis events only",
    )
    args = parser.parse_args(argv)

    data_dir = args.data_dir or default_data_dir()
    out_dir = args.out_dir or (data_dir / "jd")
    redis = connect_redis(args.redis_url)

    on_evidence = None
    if not args.skip_graph:
        try:
            on_evidence = _evidence_writer()
        except Exception as exc:
            print(f"graph skipped: {exc}", file=sys.stderr)

    stats = run_ingest(
        data_dir=data_dir,
        out_dir=out_dir,
        redis=redis,
        on_evidence=on_evidence,
    )
    flush = getattr(on_evidence, "flush", None)
    if callable(flush):
        flush()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
