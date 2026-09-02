"""Produce the reviewable per-job audit required before a graph release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app import graph
from app.pipeline.diagnostic_release import equivalent_count


def build_audit() -> dict:
    graph.init_graph()
    with graph._driver.session() as session:
        jobs = session.run("MATCH (j:Job) RETURN j.id AS id, j.name AS name, j.status AS status ORDER BY j.name").data()
    rows = []
    for job in jobs:
        job_id = job["id"]
        requires = graph.list_requires(job_id)
        evidence = graph.list_job_evidence(job_id, include_retracted=True)
        definition = graph.current_definition(job_id)
        check = graph.diagnostic_release(job_id)
        delta = graph.period_delta(job_id)
        rows.append(
            {
                **job,
                "definition_approved": bool(definition),
                "independent_source_count": len({row.get("company") for row in evidence if row.get("company")}),
                "required": len([row for row in requires if row.get("kind") == "required"]),
                "bonus": len([row for row in requires if row.get("kind") == "bonus"]),
                "watching": len(graph.get_any_job(job_id).get("watching") or []),
                "groups": sorted({row.get("group_id") for row in requires if row.get("group_id")}),
                "required_equivalent": equivalent_count(requires, kinds={"required"}),
                "formal_equivalent": equivalent_count(requires, kinds={"required", "bonus"}),
                "period_delta": delta,
                "diagnostic_release": check,
            }
        )
    return {"schema_version": "jobevolution.audit.v1", "jobs": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the current graph diagnostic audit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "jobs": len(report["jobs"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
