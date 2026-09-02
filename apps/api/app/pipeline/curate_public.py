"""用可回滚规则校准公开岗位图谱，阻止抽取噪声直接成为职业结论。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.pipeline.extract import BRAND_NAMES, BROAD_DOMAIN_NAMES, GENERIC_SKILL_NAMES

CURATION_VERSION = "public-curation-v1"
MAX_REQUIRED = 12
MAX_FORMAL = 24

_ALIASES = {
    "prompt engineering": "提示词工程",
    "promptengineering": "提示词工程",
    "提示词设计": "提示词工程",
    "llm application development": "大语言模型应用开发",
}


def canonical_name(name: str) -> str:
    text = " ".join(str(name or "").strip().split())
    return _ALIASES.get(text.casefold(), text)


def _noise_kind(name: str) -> str:
    folded = canonical_name(name).casefold()
    if folded in GENERIC_SKILL_NAMES:
        return "generic"
    if folded in BRAND_NAMES:
        return "brand"
    if folded in BROAD_DOMAIN_NAMES:
        return "broad_domain"
    return "skill"


def rank_requirements(
    rows: list[dict],
    evidence_ids: set[str],
    *,
    max_required: int = MAX_REQUIRED,
    max_formal: int = MAX_FORMAL,
) -> dict:
    """按独立来源、明确票和置信度选出有限正式要求。

    返回 selected/expired 两组原始行，调用方负责写入图谱。相同别名只保留
    来源更多的一条；通用素质、模型品牌和来源失效的边全部退出正式要求。
    """
    best: dict[str, tuple[tuple, dict]] = {}
    for row in rows:
        sid = str(row.get("skill_id") or "")
        name = canonical_name(row.get("name") or sid)
        sources = sorted({str(source) for source in row.get("sources") or [] if str(source) in evidence_ids})
        if not sid or not sources or _noise_kind(name) in {"generic", "brand"}:
            continue
        candidate = {**row, "name": name, "sources": sources}
        source_count = len(sources)
        explicit = 1 if row.get("kind") == "required" else 0
        broad = 1 if _noise_kind(name) == "broad_domain" else 0
        confidence = float(row.get("confidence") or 0)
        score = (source_count, explicit, -broad, confidence, name.casefold())
        previous = best.get(name)
        if previous is None or score > previous[0]:
            best[name] = (score, candidate)

    ordered = [item[1] for item in sorted(best.values(), key=lambda item: item[0], reverse=True)]
    selected: list[dict] = []
    for index, row in enumerate(ordered):
        if index < max_required:
            selected.append({**row, "kind": "required"})
        elif index < max_formal:
            selected.append({**row, "kind": "bonus"})
    selected_ids = {row["skill_id"] for row in selected}
    expired = [row for row in rows if str(row.get("skill_id") or "") not in selected_ids]
    return {
        "selected": selected,
        "expired": expired,
        "counts": {
            "required": sum(row["kind"] == "required" for row in selected),
            "formal": len(selected),
        },
    }


def _definition_claim(job_name: str, events: list[dict], evidence_ids: set[str]) -> list[dict]:
    snippets: list[str] = []
    sources: set[str] = set()
    for event in events:
        if event.get("review") not in {"approved", "auto_passed"}:
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        excerpt = " ".join(str(payload.get("excerpt") or "").split())
        valid_sources = {str(source) for source in payload.get("sources") or [] if str(source) in evidence_ids}
        if excerpt and valid_sources:
            snippets.append(excerpt[:120])
            sources.update(valid_sources)
        if len(sources) >= 2 and len(snippets) >= 2:
            break
    if len(sources) < 2:
        return []
    text = f"{job_name}的招聘信息主要围绕：" + "；".join(dict.fromkeys(snippets[:3]))
    return [{"type": "responsibility", "text": text[:360], "sources": sorted(sources)}]


def curate_public_jobs(*, dry_run: bool = False, period: str = "") -> dict:
    from app import graph

    graph.init_graph()
    with graph._driver.session() as session:
        jobs = session.run(
            "MATCH (j:Job) WHERE j.status IN ['emerging', 'formed'] RETURN j.id AS id, j.name AS name ORDER BY j.name"
        ).data()
    at = datetime.now(timezone.utc).isoformat()
    report: list[dict] = []
    for job in jobs:
        job_id = job["id"]
        evidence = graph.list_job_evidence(job_id, include_retracted=True)
        evidence_ids = {str(row.get("id")) for row in evidence if row.get("id") and not row.get("retracted")}
        rows = graph.list_requires(job_id)
        ranked = rank_requirements(rows, evidence_ids)
        claims = _definition_claim(job["name"], graph.list_job_events(job_id), evidence_ids)
        item = {
            "job_id": job_id,
            "name": job["name"],
            "before": {"formal": len(rows)},
            "after": ranked["counts"],
            "definition_claims": len(claims),
        }
        report.append(item)
        if dry_run:
            continue
        with graph._driver.session() as session:
            for row in ranked["selected"]:
                session.run(
                    "MATCH (j:Job {id: $job_id})-[r:REQUIRES]->(s:Skill {id: $skill_id}) "
                    "SET s.name = $name, r.kind = $kind, r.sources = $sources, "
                    "r.curation_version = $version, r.valid_to = null",
                    job_id=job_id, skill_id=row["skill_id"], name=row["name"], kind=row["kind"],
                    sources=row["sources"], version=CURATION_VERSION,
                )
            for row in ranked["expired"]:
                session.run(
                    "MATCH (j:Job {id: $job_id})-[r:REQUIRES]->(s:Skill {id: $skill_id}) "
                    "WHERE r.valid_to IS NULL SET r.valid_to = datetime($at), r.curation_version = $version",
                    job_id=job_id, skill_id=row.get("skill_id") or "", at=at, version=CURATION_VERSION,
                )
        if claims:
            event_id = f"curation-{CURATION_VERSION}-{job_id}"
            graph.apply_definition_claims(job_id, claims, event_id=event_id)
    release = None
    if not dry_run:
        release = graph.publish_graph_release(period=period or at[:10], metadata={"curation_version": CURATION_VERSION})
    return {"version": CURATION_VERSION, "dry_run": dry_run, "jobs": report, "release": release}


def main() -> int:
    parser = argparse.ArgumentParser(description="校准公开岗位要求并生成可诊断发布")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--period", default="")
    args = parser.parse_args()
    print(json.dumps(curate_public_jobs(dry_run=args.dry_run, period=args.period), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
