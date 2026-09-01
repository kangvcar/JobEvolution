from __future__ import annotations

from app.matching.bands import PATH_MAX, band_of, cover_required, match_score, next_cut, shift_set

WATCHING_COPY = "市场开始提，还没进要求，不算缺口"


def compare_job(requires: list[dict], resume_skills: list[dict]) -> dict:
    """requires: kind, skill_id, name, proficiency, excerpt.
    resume_skills: skill_id, name, proficiency (optional).
    """
    by_id = {row["skill_id"]: row for row in resume_skills if row.get("skill_id")}
    required = [row for row in requires if row.get("kind") != "bonus"]
    bonus = [row for row in requires if row.get("kind") == "bonus"]
    groups: dict[str, list[dict]] = {}
    for row in required:
        if row.get("group_id"):
            groups.setdefault(str(row["group_id"]), []).append(row)
    req_full = float(len(required) - sum(len(rows) - 1 for rows in groups.values()))
    bonus_full = float(len(bonus))
    req_cover = 0.0
    bonus_cover = 0.0
    gaps: list[dict] = []
    half: list[dict] = []
    covered: list[dict] = []
    ledger: list[dict] = []
    shift_items: list[dict] = []

    seen_groups: set[str] = set()
    for row in required:
        group_id = str(row.get("group_id") or "")
        if group_id:
            if group_id in seen_groups:
                continue
            seen_groups.add(group_id)
            members = groups[group_id]
            member_values = [cover_required((by_id.get(m["skill_id"]) or {}).get("proficiency") if m["skill_id"] in by_id else None, m.get("proficiency"), m["skill_id"] in by_id) for m in members]
            minimum = max(1, int(row.get("min_required") or 1))
            value = min(1.0, sum(sorted(member_values, reverse=True)[:minimum]) / minimum)
            req_cover += value
            if value < 1:
                item = {"skill_id": row["skill_id"], "name": row.get("name") or row["skill_id"], "excerpt": row.get("excerpt") or "", "cover": value, "group_id": group_id, "min_required": minimum}
                gaps.append(item)
                shift_items.extend({"id": m["skill_id"], "delta": (1.0 - value), "name": m.get("name") or m["skill_id"], "excerpt": m.get("excerpt") or "", "why": "要求组缺口"} for m in members if m["skill_id"] not in by_id)
            else:
                covered.extend({"skill_id": m["skill_id"], "name": m.get("name") or m["skill_id"], "excerpt": m.get("excerpt") or "", "cover": 1.0, "group_id": group_id, "required_proficiency": m.get("proficiency"), "resume_proficiency": (by_id.get(m["skill_id"]) or {}).get("proficiency")} for m in members)
            ledger.append({"skill_id": row["skill_id"], "name": row.get("name") or row["skill_id"], "cover": value, "side": "required", "group_id": group_id, "min_required": minimum})
            continue
        sid = row["skill_id"]
        got = by_id.get(sid)
        value = cover_required(
            None if got is None else got.get("proficiency"),
            row.get("proficiency"),
            got is not None,
        )
        req_cover += value
        item = {
            "skill_id": sid,
            "name": row.get("name") or sid,
            "excerpt": row.get("excerpt") or "",
            "cover": value,
            "required_proficiency": row.get("proficiency"),
            "resume_proficiency": got.get("proficiency") if got else None,
        }
        ledger.append({**item, "side": "required"})
        if value == 0:
            gaps.append(item)
            shift_items.append({"id": sid, "delta": 1.0, **item, "why": "缺口"})
        elif value == 0.5:
            half.append(item)
            gaps.append(item)
            shift_items.append({"id": sid, "delta": 0.5, **item, "why": "半档"})
        else:
            covered.append(item)

    for row in bonus:
        sid = row["skill_id"]
        got = by_id.get(sid)
        if got is not None:
            bonus_cover += 1.0
            covered.append(
                {
                    "skill_id": sid,
                    "name": row.get("name") or sid,
                    "excerpt": row.get("excerpt") or "",
                    "cover": 1.0,
                    "required_proficiency": row.get("proficiency"),
                    "resume_proficiency": got.get("proficiency") if got else None,
                }
            )
        ledger.append(
            {
                "skill_id": sid,
                "name": row.get("name") or sid,
                "cover": 1.0 if got is not None else 0.0,
                "side": "bonus",
            }
        )

    score = match_score(
        req_cover=req_cover,
        bonus_cover=bonus_cover,
        req_full=req_full,
        bonus_full=bonus_full,
    )
    order = shift_set(
        shift_items,
        req_cover=req_cover,
        bonus_cover=bonus_cover,
        req_full=req_full,
        bonus_full=bonus_full,
        score=score,
    )
    by_shift = {row["id"]: row for row in shift_items}
    target = next_cut(score)
    path = []
    for sid in order[:PATH_MAX]:
        row = by_shift[sid]
        why = row["why"]
        if target is not None:
            lifted = match_score(
                req_cover=req_cover + row["delta"],
                bonus_cover=bonus_cover,
                req_full=req_full,
                bonus_full=bonus_full,
            )
            if lifted / 100.0 >= target:
                why = "换档"
        path.append(
            {
                "skill_id": sid,
                "name": row["name"],
                "excerpt": row.get("excerpt") or "",
                "why": why,
                "url": "",
            }
        )
    extra = [
        row
        for row in resume_skills
        if row.get("skill_id") and row["skill_id"] not in {r["skill_id"] for r in requires}
    ]
    return {
        "score": score,
        "band": band_of(score),
        "req_cover": req_cover,
        "req_full": req_full,
        "half": half,
        "gaps": gaps,
        "covered": covered,
        "path": path,
        "shift_ids": order,
        "ledger": ledger,
        "extra": extra,
        "watching_copy": WATCHING_COPY,
    }
