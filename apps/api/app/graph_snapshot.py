"""Portable, reviewed graph snapshot export/import."""
from __future__ import annotations

import hashlib
import json
import subprocess
import re
from pathlib import Path

from app import graph
from app.releases import write_guard

SCHEMA = "jobevolution.snapshot.v1"
COLLECTIONS = {"jobs": "Job", "skills": "Skill", "evidence": "Evidence", "events": "EvolutionEvent",
               "requirement_versions": "RequirementVersion", "requirement_groups": "RequirementGroup",
               "definitions": "JobDefinitionVersion", "claims": "DefinitionClaim", "skill_merges": "SkillMerge",
               "domains": "Domain", "categories": "SkillCategory", "releases": "GraphRelease", "pointers": "GraphPointer",
               "proposals": "ReviewProposal", "decisions": "ReviewDecision", "bulk_decisions": "BulkReviewDecision"}


def _encode(value):
    from neo4j.time import Date, DateTime, Time, Duration
    if isinstance(value, (Date, DateTime, Time, Duration)):
        return {"__neo4j_type__": type(value).__name__, "value": value.iso_format()}
    raise TypeError(f"unsupported snapshot value: {type(value).__name__}")


def _decode(value):
    from neo4j import time
    if set(value) == {"__neo4j_type__", "value"} and value["__neo4j_type__"] in {"Date", "DateTime", "Time", "Duration"}:
        return getattr(time, value["__neo4j_type__"]).from_iso_format(value["value"])
    return value


@write_guard
def export_snapshot(path: str | Path, *, slim: bool = False) -> dict:
    """导出整图。slim=True 时只保留公开指针指向那一份 GraphRelease 的预计算快照，
    其余历史 release 节点保留 id / period / metadata 但清空 snapshot，避免文件膨胀到数百 MB。"""
    graph.init_graph()
    with graph._driver.session() as s:
        jobs = s.run("MATCH (j:Job) RETURN j{.*} AS row").data()
        skills = s.run("MATCH (n:Skill) RETURN n{.*} AS row").data()
        evidence = s.run("MATCH (n:Evidence) RETURN n{.*} AS row").data()
        events = s.run("MATCH (n:EvolutionEvent) RETURN n{.*} AS row").data()
        versions = s.run("MATCH (n:RequirementVersion) RETURN n{.*} AS row").data()
        groups = s.run("MATCH (n:RequirementGroup) RETURN n{.*} AS row").data()
        definitions = s.run("MATCH (n:JobDefinitionVersion) RETURN n{.*} AS row").data()
        claims = s.run("MATCH (n:DefinitionClaim) RETURN n{.*} AS row").data()
        skill_merges = s.run("MATCH (n:SkillMerge) RETURN n{.*} AS row").data()
        relationships = s.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS src_label, a.id AS src_id, type(r) AS type, properties(r) AS props, labels(b)[0] AS dst_label, b.id AS dst_id").data()
        extra = {key: [row["row"] for row in s.run(f"MATCH (n:{label}) RETURN properties(n) AS row")]
                 for key, label in COLLECTIONS.items() if key in {"domains", "categories", "releases", "pointers", "proposals", "decisions", "bulk_decisions"}}
    evidence_rows = [x["row"] for x in evidence]
    if slim:
        public_id = next((row.get("release_id") for row in extra.get("pointers", []) if row.get("id") == "public"), None)
        for row in extra.get("releases", []):
            if row.get("id") != public_id:
                row.pop("snapshot", None)
    payload = {
        "schema_version": SCHEMA,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "evidence_hash": hashlib.sha256(json.dumps(evidence_rows, ensure_ascii=False, sort_keys=True, default=_encode).encode()).hexdigest(),
        **extra,
        "jobs": [x["row"] for x in jobs], "skills": [x["row"] for x in skills],
        "evidence": evidence_rows, "events": [x["row"] for x in events],
        "requirement_versions": [x["row"] for x in versions], "requirement_groups": [x["row"] for x in groups],
        "definitions": [x["row"] for x in definitions], "claims": [x["row"] for x in claims],
        "skill_merges": [x["row"] for x in skill_merges],
        "relationships": [dict(x) for x in relationships],
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_encode), encoding="utf-8")
    temporary.replace(destination)
    return {"schema_version": SCHEMA, "counts": {key: len(value) for key, value in payload.items() if isinstance(value, list)}}


@write_guard
def import_snapshot(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"), object_hook=_decode)
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("unsupported snapshot schema")
    evidence = payload.get("evidence") or []
    if hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=_encode).encode()).hexdigest() != payload.get("evidence_hash"):
        raise ValueError("snapshot evidence hash mismatch")
    graph.init_graph()
    known = {(label, row.get("id")) for key, label in COLLECTIONS.items() for row in payload.get(key) or []}
    # 旧快照由初始化提供固定领域和分类。
    known.update(("Domain", row["id"]) for row in graph.DOMAINS)
    known.update(("SkillCategory", key) for key in graph.SKILL_CATEGORIES)
    for rel in payload.get("relationships") or []:
        if (rel.get("src_label"), rel.get("src_id")) not in known or (rel.get("dst_label"), rel.get("dst_id")) not in known or not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(rel.get("type") or "")):
            raise ValueError("snapshot relationship has invalid type or missing endpoint")
    with graph._driver.session() as s:
      with s.begin_transaction() as tx:
        if tx.run("MATCH (n) WHERE NOT n:Domain AND NOT n:SkillCategory RETURN count(n) AS n").single()["n"]:
            raise ValueError("restore requires an empty graph; restore into a new database first")
        for key, label in COLLECTIONS.items():
            rows = payload.get(key)
            for row in rows or []:
                rid = row.get("id")
                if not rid:
                    raise ValueError("snapshot node has no id")
                props = {key: value for key, value in row.items() if key != "id" and value is not None}
                tx.run(f"MERGE (n:{label} {{id: $id}}) SET n += $props", id=rid, props=props)
        for rel in payload.get("relationships") or []:
            if not rel.get("src_id") or not rel.get("dst_id"):
                continue
            rel_type = "".join(ch for ch in str(rel.get("type") or "") if ch.isalnum() or ch == "_")
            if not rel_type:
                continue
            tx.run(f"MATCH (a:{rel['src_label']} {{id: $src}}), (b:{rel['dst_label']} {{id: $dst}}) MERGE (a)-[r:{rel_type}]->(b) SET r += $props", src=rel["src_id"], dst=rel["dst_id"], props=rel.get("props") or {})
        tx.commit()
    return {"schema_version": SCHEMA, "imported": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("export", "import"))
    parser.add_argument("path")
    parser.add_argument("--slim", action="store_true", help="export: keep only the public release's precomputed snapshot")
    args = parser.parse_args()
    print(json.dumps(export_snapshot(args.path, slim=args.slim) if args.mode == "export" else import_snapshot(args.path), ensure_ascii=False))
