"""Portable, reviewed graph snapshot export/import."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from app import graph

SCHEMA = "jobevolution.snapshot.v1"


def export_snapshot(path: str | Path) -> dict:
    graph.init_graph()
    with graph._driver.session() as s:
        jobs = s.run("MATCH (j:Job) RETURN j{.*} AS row").data()
        skills = s.run("MATCH (n:Skill) RETURN n{.*} AS row").data()
        evidence = s.run("MATCH (n:Evidence) WHERE coalesce(n.retracted,false)=false RETURN n{.*} AS row").data()
        events = s.run("MATCH (n:EvolutionEvent) RETURN n{.*} AS row").data()
        versions = s.run("MATCH (n:RequirementVersion) WHERE coalesce(n.retracted,false)=false RETURN n{.*} AS row").data()
        groups = s.run("MATCH (n:RequirementGroup) RETURN n{.*} AS row").data()
        definitions = s.run("MATCH (n:JobDefinitionVersion) RETURN n{.*} AS row").data()
        claims = s.run("MATCH (n:DefinitionClaim) RETURN n{.*} AS row").data()
        skill_merges = s.run("MATCH (n:SkillMerge) RETURN n{.*} AS row").data()
        relationships = s.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS src_label, a.id AS src_id, type(r) AS type, properties(r) AS props, labels(b)[0] AS dst_label, b.id AS dst_id").data()
    evidence_rows = [x["row"] for x in evidence]
    payload = {
        "schema_version": SCHEMA,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "evidence_hash": hashlib.sha256(json.dumps(evidence_rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "jobs": [x["row"] for x in jobs], "skills": [x["row"] for x in skills],
        "evidence": evidence_rows, "events": [x["row"] for x in events],
        "requirement_versions": [x["row"] for x in versions], "requirement_groups": [x["row"] for x in groups],
        "definitions": [x["row"] for x in definitions], "claims": [x["row"] for x in claims],
        "skill_merges": [x["row"] for x in skill_merges],
        "relationships": [dict(x) for x in relationships],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"schema_version": SCHEMA, "counts": {key: len(value) for key, value in payload.items() if isinstance(value, list)}}


def import_snapshot(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("unsupported snapshot schema")
    evidence = payload.get("evidence") or []
    if hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest() != payload.get("evidence_hash"):
        raise ValueError("snapshot evidence hash mismatch")
    graph.init_graph()
    with graph._driver.session() as s:
        for label, rows in (("Job", payload.get("jobs")), ("Skill", payload.get("skills")), ("Evidence", evidence), ("EvolutionEvent", payload.get("events")), ("RequirementVersion", payload.get("requirement_versions")), ("RequirementGroup", payload.get("requirement_groups")), ("JobDefinitionVersion", payload.get("definitions")), ("DefinitionClaim", payload.get("claims")), ("SkillMerge", payload.get("skill_merges"))):
            for row in rows or []:
                rid = row.get("id")
                if not rid:
                    continue
                props = {key: value for key, value in row.items() if key != "id" and value is not None}
                s.run(f"MERGE (n:{label} {{id: $id}}) SET n += $props", id=rid, props=props)
        for rel in payload.get("relationships") or []:
            if not rel.get("src_id") or not rel.get("dst_id"):
                continue
            rel_type = "".join(ch for ch in str(rel.get("type") or "") if ch.isalnum() or ch == "_")
            if not rel_type:
                continue
            s.run(f"MATCH (a:{rel['src_label']} {{id: $src}}), (b:{rel['dst_label']} {{id: $dst}}) MERGE (a)-[r:{rel_type}]->(b) SET r += $props", src=rel["src_id"], dst=rel["dst_id"], props=rel.get("props") or {})
    return {"schema_version": SCHEMA, "imported": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("export", "import"))
    parser.add_argument("path")
    args = parser.parse_args()
    print(json.dumps(export_snapshot(args.path) if args.mode == "export" else import_snapshot(args.path), ensure_ascii=False))
