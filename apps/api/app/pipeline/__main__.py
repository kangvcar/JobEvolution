"""Extract local JD snapshots into the graph. python -m app.pipeline"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from app.targets import JOB_TARGET_NAMES

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


def select_snapshots(jd_dir: Path, per_job: int) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(jd_dir.glob("jd-*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = match_target(doc.get("title") or "")
        if not name:
            continue
        companies = {row.get("company") for row in buckets[name]}
        if doc.get("company") in companies:
            continue
        if len(buckets[name]) >= per_job:
            continue
        buckets[name].append(doc)
    out: list[dict] = []
    for name in JOB_TARGET_NAMES:
        out.extend(buckets[name])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract JD snapshots into the graph")
    parser.add_argument("--jd-dir", type=Path, default=None)
    parser.add_argument("--per-job", type=int, default=8)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--passthrough", action="store_true")
    args = parser.parse_args(argv)

    jd_dir = args.jd_dir or default_jd_dir()
    snaps = select_snapshots(jd_dir, max(1, args.per_job))
    print(json.dumps({"jd_dir": str(jd_dir), "selected": len(snaps)}, ensure_ascii=False))
    if not snaps:
        return 1

    from app import graph
    from app.pipeline.gate import run_extract_and_gate, set_passthrough

    if graph._driver is None:
        graph.init_graph()
    if args.passthrough:
        set_passthrough(True)
    events = run_extract_and_gate(snaps, workers=args.workers)
    pending = sum(1 for e in events if e.get("review") == "pending")
    auto = sum(1 for e in events if e.get("review") == "auto_passed")
    failed = sum(1 for e in events if e.get("kind") == "extract_failed")
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
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
