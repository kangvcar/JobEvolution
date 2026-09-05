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
    retracted = []
    for row in requires:
        source_ids = [str(source) for source in row.get("sources") or [] if source]
        if not source_ids:
            missing.append(row.get("skill_id") or row.get("name") or "")
        for source_id in source_ids:
            if source_id not in by_evidence:
                missing.append(row.get("skill_id") or source_id)
            if by_evidence.get(source_id, {}).get("retracted"):
                retracted.append(source_id)
        excerpt = (row.get("excerpt") or "").strip()
        if not excerpt or not any(excerpt in (by_evidence.get(sid, {}).get("body") or "") for sid in source_ids):
            missing.append(row.get("skill_id") or "excerpt")
    for claim in claims:
        ids = claim.get("sources") or []
        excerpt = (claim.get("excerpt") or claim.get("text") or "").strip()
        if not ids or any(sid not in by_evidence or by_evidence[sid].get("retracted") for sid in ids):
            missing.append(claim.get("id") or "definition")
        else:
            # 旧版已批准定义用固定前缀连接原文，逐个核对其原文声明。
            fragments = excerpt.split("的招聘信息主要围绕：", 1)[-1].split("；")
            if any(not fragment or not any(fragment in (by_evidence[sid].get("body") or "") for sid in ids)
                   for fragment in fragments):
                missing.append(claim.get("id") or "definition_excerpt")
    groups = defaultdict(list)
    for row in requires:
        if row.get("group_id"):
            groups[row["group_id"]].append(row)
    for gid, rows in groups.items():
        minima = {int(row.get("min_required") or 1) for row in rows}
        if len(minima) != 1 or not 1 <= next(iter(minima)) <= len(rows) or len({row.get("kind") for row in rows}) != 1:
            errors.append({"code": "invalid_requirement_group", "group_id": gid})
    if missing:
        errors.append({"code": "evidence_missing", "items": sorted(set(missing))})
    if retracted:
        errors.append({"code": "evidence_retracted", "items": sorted(set(retracted))})
    duplicates = [sid for sid, count in Counter(row.get("skill_id") for row in requires if row.get("skill_id")).items() if count > 1]
    if duplicates:
        errors.append({"code": "duplicate_requirement", "items": sorted(duplicates)})
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

    anomaly_codes = {"required_delta_anomaly", "formal_delta_anomaly", "required_count_exceeded", "formal_count_exceeded"}
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
