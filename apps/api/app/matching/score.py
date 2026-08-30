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
    req_full = float(len(required))
    bonus_full = float(len(bonus))
    req_cover = 0.0
    bonus_cover = 0.0
    gaps: list[dict] = []
    half: list[dict] = []
    covered: list[dict] = []
    ledger: list[dict] = []
    shift_items: list[dict] = []

    for row in required:
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
