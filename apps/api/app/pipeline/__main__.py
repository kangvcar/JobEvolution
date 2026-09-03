"""Extract local JD snapshots into the graph. python -m app.pipeline"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from app.pipeline.constants import (
    ALIAS_CAP,
    ALIAS_PRE_FILTER,
    FAT_JOB_SOURCES,
    FAT_SLICE_CAP,
)
from app.targets import JOB_TARGET_NAMES

CONTEST_PAIR = ("大模型应用工程师", "Agent 工程师")
FAT_JOBS = ("算法工程师", "数据分析师", "数据工程师")


def default_jd_dir() -> Path:
    env = os.environ.get("JD_DIR")
    if env:
        return Path(env)
    docker = Path("/app/data/jd")
    if docker.is_dir():
        return docker
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        candidate = base / "data" / "jd"
        if candidate.is_dir():
            return candidate
    return Path("data/jd")


def match_target(title: str) -> str | None:
    compact = (title or "").replace(" ", "")
    for name in sorted(JOB_TARGET_NAMES, key=len, reverse=True):
        token = name.replace(" ", "")
        if token and token in compact:
            return name
    return None


def match_alias(title: str) -> bool:
    compact = (title or "").replace(" ", "")
    return any(token and token in compact for token in ALIAS_PRE_FILTER)


def _dedup_companies(docs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    picked: list[dict] = []
    for doc in docs:
        company = doc.get("company") or ""
        if not company or company in seen:
            continue
        seen.add(company)
        picked.append(doc)
    return picked


def _two_slices(docs: list[dict]) -> list[dict]:
    half = len(docs) // 2
    old_pick = _dedup_companies(docs[:half])[:FAT_SLICE_CAP]
    new_pick = _dedup_companies(list(reversed(docs[half:])))[:FAT_SLICE_CAP]
    return old_pick + new_pick


def select_snapshots(jd_dir: Path) -> list[dict]:
    targets: dict[str, list[dict]] = defaultdict(list)
    alias: list[dict] = []
    for path in sorted(jd_dir.glob("jd-*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = match_target(doc.get("title") or "")
        if name:
            targets[name].append(doc)
        elif match_alias(doc.get("title") or ""):
            alias.append(doc)
    out: list[dict] = []
    for name in JOB_TARGET_NAMES:
        docs = sorted(targets.get(name) or [], key=lambda row: row.get("observed_at") or "")
        if not docs:
            continue
        deduped = _dedup_companies(docs)
        if name in CONTEST_PAIR or name not in FAT_JOBS or len(deduped) <= FAT_JOB_SOURCES:
            out.extend(deduped)
        else:
            out.extend(_two_slices(docs))
    out.extend({**doc, "alias_candidate": True} for doc in _dedup_companies(alias)[:ALIAS_CAP])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract JD snapshots into the graph")
    parser.add_argument("--jd-dir", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--passthrough", action="store_true")
    parser.add_argument("--no-cache", action="store_true", help="ignore the per-snapshot extract cache")
    args = parser.parse_args(argv)

    jd_dir = args.jd_dir or default_jd_dir()
    snaps = select_snapshots(jd_dir)
    print(json.dumps({"jd_dir": str(jd_dir), "selected": len(snaps)}, ensure_ascii=False))
    if not snaps:
        from app.ops_status import record

        record("pipeline", "failed", events=0, failed=0, error="no JD snapshots")
        return 1

    from app import graph
    from app.pipeline.gate import run_extract_and_gate, set_passthrough

    graph.init_graph()
    if args.passthrough:
        set_passthrough(True)
    from app.ops_status import record

    try:
        events = run_extract_and_gate(snaps, workers=args.workers, cache=not args.no_cache)
    except Exception as exc:
        record("pipeline", "failed", events=0, failed=1, error=str(exc)[:300])
        print(json.dumps({"events": 0, "pending": 0, "auto_passed": 0, "extract_failed": 1, "error": str(exc)[:300]}, ensure_ascii=False))
        return 1
    pending = sum(1 for e in events if e.get("review") == "pending")
    auto = sum(1 for e in events if e.get("review") == "auto_passed")
    failed = sum(1 for e in events if e.get("kind") == "extract_failed")
    record("pipeline", "failed" if failed else "success", events=len(events), failed=failed)
    release = None
    if failed == 0:
        release = graph.publish_graph_release(period=max((row.get("observed_at") or "" for row in snaps), default=""))
        record("publish", "success", release=release.get("id"))
    with graph._driver.session() as session:
        jobs = session.run(
            "MATCH (j:Job) RETURN j.name AS name, j.status AS status ORDER BY j.name"
        ).data()
        skills = session.run("MATCH (s:Skill) RETURN count(s) AS n").single()["n"]
        req = session.run("MATCH ()-[r:REQUIRES]->() RETURN count(r) AS n").single()["n"]
    print(
        json.dumps(
            {
                "events": len(events),
                "pending": pending,
                "auto_passed": auto,
                "extract_failed": failed,
                "jobs": jobs,
                "skills": skills,
                "requires": req,
                "release": release,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
