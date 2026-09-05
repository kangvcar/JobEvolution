from __future__ import annotations

from collections import Counter, defaultdict


MAX_REQUIRED_EQUIVALENT = 12
MAX_FORMAL_EQUIVALENT = 24


def equivalent_count(rows: list[dict], *, kinds: set[str] | None = None) -> int:
    selected = [row for row in rows if kinds is None or row.get("kind") in kinds]
    groups: dict[str, list[dict]] = defaultdict(list)
    standalone: set[str] = set()
    for row in selected:
        gid = str(row.get("group_id") or "")
        if gid:
            groups[gid].append(row)
        else:
            standalone.add(str(row.get("skill_id") or ""))
    return len({sid for sid in standalone if sid}) + sum(
        max(1, int(rows[0].get("min_required") or 1)) for rows in groups.values()
    )


DEFINITION_PREFIX = "的招聘信息主要围绕："


def claim_fragments(claim: dict) -> tuple[str, list[str]]:
    """把定义声明拆成可逐条核对的原文片段，返回 (前缀, 片段列表)。

    旧版已批准定义用固定前缀连接原文片段，前缀本身不是证据原文。
    """
    excerpt = (claim.get("excerpt") or claim.get("text") or "").strip()
    prefix = ""
    body = excerpt
    if DEFINITION_PREFIX in excerpt:
        head, body = excerpt.split(DEFINITION_PREFIX, 1)
        prefix = head + DEFINITION_PREFIX
    fragments = [fragment.strip() for fragment in body.split("；")]
    return prefix, [fragment for fragment in fragments if fragment]


def check_claim_fragments(claim: dict, by_evidence: dict[str, dict]) -> list[dict]:
    """逐片段核对定义声明：每个片段至少要在一个未撤回来源的原文里逐字出现。"""
    ids = [str(sid) for sid in claim.get("sources") or [] if sid]
    bodies = {sid: (by_evidence.get(sid, {}).get("body") or "") for sid in ids}
    _, fragments = claim_fragments(claim)
    out = []
    for fragment in fragments:
        supported_by = [sid for sid, body in bodies.items() if body and fragment in body]
        out.append({"text": fragment, "supported": bool(supported_by), "sources": supported_by})
    return out


def validate_diagnostic_release(
    *,
    job_id: str,
    definition: list[dict],
    requires: list[dict],
    evidence: list[dict],
    previous_requires: list[dict] | None = None,
    override_reason: str = "",
) -> dict:
    errors: list[dict] = []
    claims = [claim for claim in definition if (claim.get("text") or "").strip()]
    if not claims:
        errors.append({"code": "definition_missing", "message": "岗位定义为空或尚未批准"})
    required = equivalent_count(requires, kinds={"required"})
    formal = equivalent_count(requires, kinds={"required", "bonus"})
    if required == 0:
        errors.append({"code": "required_group_missing", "message": "没有有效必备要求"})
    by_evidence = {str(row.get("id")): row for row in evidence if row.get("id")}
    missing = []
    missing_details: list[dict] = []
    retracted = []
    for row in requires:
        label = row.get("skill_id") or row.get("name") or ""
        reasons: list[str] = []
        source_ids = [str(source) for source in row.get("sources") or [] if source]
        if not source_ids:
            missing.append(label)
            reasons.append("no_sources")
        for source_id in source_ids:
            if source_id not in by_evidence:
                missing.append(row.get("skill_id") or source_id)
                reasons.append("source_unknown")
            if by_evidence.get(source_id, {}).get("retracted"):
                retracted.append(source_id)
        excerpt = (row.get("excerpt") or "").strip()
        bodies = [(by_evidence.get(sid, {}).get("body") or "") for sid in source_ids]
        if not excerpt:
            missing.append(row.get("skill_id") or "excerpt")
            reasons.append("excerpt_missing")
        elif any(bodies) and not any(excerpt in body for body in bodies):
            missing.append(row.get("skill_id") or "excerpt")
            reasons.append("excerpt_not_in_evidence")
        if reasons:
            missing_details.append({
                "target": "requirement",
                "id": row.get("skill_id") or "",
                "name": row.get("name") or row.get("skill_id") or "",
                "kind": row.get("kind"),
                "excerpt": excerpt,
                "reasons": sorted(set(reasons)),
            })
    for claim in claims:
        ids = [str(sid) for sid in claim.get("sources") or [] if sid]
        claim_id = claim.get("id") or "definition"
        if ids and any(sid not in by_evidence or by_evidence[sid].get("retracted") for sid in ids):
            missing.append(claim_id)
            missing_details.append({
                "target": "claim",
                "id": claim_id,
                "text": claim.get("text") or "",
                "reasons": ["source_unavailable"],
                "fragments": check_claim_fragments(claim, by_evidence),
            })
        elif ids:
            fragments = check_claim_fragments(claim, by_evidence)
            if not fragments or any(not fragment["supported"] for fragment in fragments):
                missing.append(claim.get("id") or "definition_excerpt")
                missing_details.append({
                    "target": "claim",
                    "id": claim_id,
                    "text": claim.get("text") or "",
                    "reasons": ["fragment_not_in_evidence"],
                    "fragments": fragments,
                })
    groups = defaultdict(list)
    for row in requires:
        if row.get("group_id"):
            groups[row["group_id"]].append(row)
    for gid, rows in groups.items():
        minima = {int(row.get("min_required") or 1) for row in rows}
        kinds = {row.get("kind") for row in rows}
        reasons = []
        if len(kinds) != 1:
            reasons.append("mixed_kind")
        if len(minima) != 1 or not 1 <= next(iter(minima)) <= len(rows):
            reasons.append("min_required_out_of_range")
        if reasons:
            errors.append({
                "code": "invalid_requirement_group",
                "group_id": gid,
                "reasons": reasons,
                "min_required": sorted(minima)[0] if len(minima) == 1 else None,
                "members": [
                    {"skill_id": row.get("skill_id"), "name": row.get("name") or row.get("skill_id"), "kind": row.get("kind")}
                    for row in rows
                ],
            })
    if missing:
        errors.append({"code": "evidence_missing", "items": sorted(set(missing)), "details": missing_details})
    if retracted:
        errors.append({"code": "evidence_retracted", "items": sorted(set(retracted))})
    names = {row.get("skill_id"): row.get("name") for row in requires if row.get("skill_id")}
    duplicates = [sid for sid, count in Counter(row.get("skill_id") for row in requires if row.get("skill_id")).items() if count > 1]
    if duplicates:
        errors.append({
            "code": "duplicate_requirement",
            "items": sorted(duplicates),
            "details": [{"skill_id": sid, "name": names.get(sid) or sid} for sid in sorted(duplicates)],
        })
    if required > MAX_REQUIRED_EQUIVALENT:
        errors.append({"code": "required_count_exceeded", "count": required, "limit": MAX_REQUIRED_EQUIVALENT})
    if formal > MAX_FORMAL_EQUIVALENT:
        errors.append({"code": "formal_count_exceeded", "count": formal, "limit": MAX_FORMAL_EQUIVALENT})

    previous_required = equivalent_count(previous_requires or [], kinds={"required"})
    previous_formal = equivalent_count(previous_requires or [], kinds={"required", "bonus"})
    required_delta = max(0, required - previous_required)
    formal_delta = max(0, formal - previous_formal)
    if previous_requires and required_delta > max(3, previous_required * 0.5):
        errors.append({"code": "required_delta_anomaly", "delta": required_delta, "previous": previous_required})
    if previous_requires and formal_delta > max(5, previous_formal * 0.5):
        errors.append({"code": "formal_delta_anomaly", "delta": formal_delta, "previous": previous_formal})

    anomaly_codes = {"required_delta_anomaly", "formal_delta_anomaly"}
    overridden = bool(override_reason.strip())
    if overridden:
        errors = [error for error in errors if error.get("code") not in anomaly_codes]
    return {
        "job_id": job_id,
        "ok": not errors,
        "errors": errors,
        "counts": {
            "required_equivalent": required,
            "formal_equivalent": formal,
            "required_delta": required_delta,
            "formal_delta": formal_delta,
        },
        "override": {"reason": override_reason.strip()} if overridden else None,
    }
