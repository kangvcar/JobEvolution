"""用可回滚规则校准公开岗位图谱，阻止抽取噪声直接成为职业结论。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.pipeline.extract import BRAND_NAMES, BROAD_DOMAIN_NAMES, GENERIC_SKILL_NAMES
from app.pipeline.diagnostic_release import DEFINITION_PREFIX, check_claim_fragments, equivalent_count

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
    要求组整组进退、整组同一 kind，计数按 min_required 记，不把组员各记一条。
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

    # 同一要求组的成员合成一个单元：原文"至少一门"的替代组只要有成员明确必备，整组按必备处理；
    # 组员被裁掉后 min_required 跟着收缩，只剩一个成员时退回独立要求。
    units: list[dict] = []
    grouped: dict[str, dict] = {}
    for score, candidate in sorted(best.values(), key=lambda item: item[0], reverse=True):
        gid = str(candidate.get("group_id") or "")
        if not gid:
            units.append({"rows": [candidate], "kind": candidate.get("kind"), "score": score})
            continue
        unit = grouped.get(gid)
        if unit is None:
            unit = {"rows": [], "kind": candidate.get("kind"), "score": score}
            grouped[gid] = unit
            units.append(unit)
        unit["rows"].append(candidate)
        if candidate.get("kind") == "required":
            unit["kind"] = "required"
    for unit in units:
        members = unit["rows"]
        if len(members) == 1:
            members[0] = {**members[0], "group_id": None, "min_required": None}
            continue
        minimum = max(1, min(int(members[0].get("min_required") or 1), len(members)))
        unit["rows"] = [{**row, "min_required": minimum} for row in members]
    units.sort(key=lambda unit: unit["score"], reverse=True)

    def unit_rows(unit: dict, kind: str) -> list[dict]:
        return [{**row, "kind": kind} for row in unit["rows"]]

    def cost(unit: dict) -> int:
        return equivalent_count(unit["rows"])

    selected: list[dict] = []
    overflow: list[dict] = []
    required_budget = max_required
    for unit in units:
        if unit["kind"] != "required":
            overflow.append(unit)
            continue
        if cost(unit) <= required_budget:
            selected.extend(unit_rows(unit, "required"))
            required_budget -= cost(unit)
        else:
            overflow.append(unit)
    remaining = max(0, max_formal - equivalent_count(selected, kinds={"required", "bonus"}))
    for unit in overflow:
        if cost(unit) > remaining:
            continue
        selected.extend(unit_rows(unit, "bonus"))
        remaining -= cost(unit)
    selected_ids = {row["skill_id"] for row in selected}
    expired = [row for row in rows if str(row.get("skill_id") or "") not in selected_ids]
    return {
        "selected": selected,
        "expired": expired,
        "counts": {
            "required": equivalent_count(selected, kinds={"required"}),
            "formal": equivalent_count(selected, kinds={"required", "bonus"}),
        },
    }


def evidence_bodies(job_id: str) -> dict[str, str]:
    """岗位未撤回证据的正文，按证据 id 索引，供定义声明逐字核对。"""
    from app import graph

    return {
        str(row.get("id")): str(row.get("body") or "")
        for row in graph.evidence_for_validation(job_id)
        if row.get("id") and not row.get("retracted")
    }


def _definition_claim(job_name: str, events: list[dict], evidence_bodies: dict[str, str]) -> list[dict]:
    """从已批准提案的原文片段拼出定义声明。

    片段必须逐字出现在至少一个未撤回来源的正文里，只挂真正包含它的来源；
    抽取模型改写过的片段不进定义，否则发布校验会以 evidence_missing 拦下整个岗位。
    """
    snippets: list[str] = []
    sources: set[str] = set()
    for event in events:
        if event.get("review") not in {"approved", "auto_passed"}:
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        raw = str(payload.get("excerpt") or "").strip()
        candidates = [raw, " ".join(raw.split())] if raw else []
        candidate_sources = [str(source) for source in payload.get("sources") or [] if str(source) in evidence_bodies]
        chosen = ""
        supported: set[str] = set()
        if candidates and candidate_sources and not any(evidence_bodies.get(sid) for sid in candidate_sources):
            # 来源正文暂不可读（快照文件缺失）时无法逐字核对，沿用来源列表，与要求边摘录检查的降级方式一致。
            chosen, supported = candidates[-1], set(candidate_sources)
        for text in candidates:
            if chosen:
                break
            supported = {sid for sid in candidate_sources if text and text in (evidence_bodies.get(sid) or "")}
            if supported:
                chosen = text
        if chosen and supported:
            snippets.append(chosen[:120])
            sources.update(supported)
        if len(sources) >= 2 and len(snippets) >= 2:
            break
    if len(sources) < 2:
        return []
    text = f"{job_name}{DEFINITION_PREFIX}" + "；".join(dict.fromkeys(snippets[:3]))
    return [{"type": "responsibility", "text": text[:360], "sources": sorted(sources)}]


from app.releases import write_guard


@write_guard
def curate_public_jobs(*, dry_run: bool = False, period: str = "", publish_release: bool = True) -> dict:
    from app import graph

    graph.init_graph()
    with graph._driver.session() as session:
        jobs = session.run(
            "MATCH (j:Job)-[:IN_DOMAIN]->(d:Domain) WHERE j.status IN ['emerging', 'formed'] RETURN j.id AS id, j.name AS name, d.id AS domain ORDER BY j.name"
        ).data()
    at = datetime.now(timezone.utc).isoformat()
    report: list[dict] = []
    for job in jobs:
        job_id = job["id"]
        evidence = graph.evidence_for_validation(job_id)
        evidence_ids = {str(row.get("id")) for row in evidence if row.get("id") and not row.get("retracted")}
        bodies = {str(row.get("id")): str(row.get("body") or "") for row in evidence if row.get("id") and not row.get("retracted")}
        rows = graph.list_requires(job_id)
        ranked = rank_requirements(rows, evidence_ids)
        claims = _definition_claim(job["name"], graph.list_job_events(job_id), bodies)
        item = {
            "job_id": job_id,
            "name": job["name"],
            "before": {
                "required": equivalent_count(rows, kinds={"required"}),
                "formal": equivalent_count(rows, kinds={"required", "bonus"}),
            },
            "after": ranked["counts"],
            "definition_claims": len(claims),
        }
        report.append(item)
        if dry_run:
            continue
        for row in ranked["selected"]:
            graph.apply_requires({
                "job_id": job_id,
                "job_name": job["name"],
                "domain": job.get("domain") or "ai",
                "skill_id": row["skill_id"],
                "skill_name": row["name"],
                "kind_edge": row["kind"],
                "proficiency": row.get("proficiency"),
                "weight": row.get("weight"),
                "levels": row.get("levels"),
                "layer": row.get("layer"),
                "confidence": row.get("confidence"),
                "sources": row["sources"],
                "excerpt": row.get("excerpt"),
                "group_id": row.get("group_id"),
                "min_required": row.get("min_required"),
                "valid_from": at,
                "curation_version": CURATION_VERSION,
            })
        graph.expire_absent_requires(
            job_id,
            [row["skill_id"] for row in ranked["selected"]],
            at,
            CURATION_VERSION,
        )
        current_definition = graph.current_definition(job_id)
        # 管理员手工修正过的定义声明由人负责，规则校准不再覆盖；
        # 已能逐字对上证据的定义也不重写，校准只补空缺和修坏的，不制造无谓的定义变更。
        by_evidence = {str(row.get("id")): row for row in evidence if row.get("id")}
        admin_owned = any(row.get("corrected_at") for row in current_definition)
        current_ok = bool(current_definition) and all(
            (fragments := check_claim_fragments(row, by_evidence)) and all(fragment["supported"] for fragment in fragments)
            for row in current_definition
        )
        if claims and not admin_owned and not current_ok and claims[0].get("text") not in {row.get("text") for row in current_definition}:
            event_id = f"curation-{CURATION_VERSION}-{job_id}"
            graph.apply_definition_claims(job_id, claims, event_id=event_id)
        from app.pipeline.status import refresh_job_status

        refresh_job_status(job_id)
    release = None
    if not dry_run and publish_release:
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
