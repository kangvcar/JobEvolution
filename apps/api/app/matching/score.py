from __future__ import annotations

from app.matching.bands import PATH_MAX, band_of, cover_required, match_score, shift_set

WATCHING_COPY = "市场开始提，还没进要求，不算缺口"


def compare_job(requires: list[dict], resume_skills: list[dict]) -> dict:
    by_id = {row["skill_id"]: row for row in resume_skills if row.get("skill_id")}
    grouped_ids = {row["skill_id"] for row in requires if row.get("group_id")}
    units: dict[tuple, list[dict]] = {}
    for row in requires:
        if not row.get("group_id") and row["skill_id"] in grouped_ids:
            continue
        key = (row.get("kind", "required"), row.get("group_id") or row["skill_id"])
        if not any(item["skill_id"] == row["skill_id"] for item in units.get(key, [])):
            units.setdefault(key, []).append(row)
    totals = {"required": 0.0, "bonus": 0.0}
    covers = {"required": 0.0, "bonus": 0.0}
    gaps, half, covered, ledger, shift_items, allowed = [], [], [], [], [], []
    for (kind, _), members in units.items():
        side = "bonus" if kind == "bonus" else "required"
        minimum = int(members[0].get("min_required") or 1) if members[0].get("group_id") else 1
        if not 1 <= minimum <= len(members):
            raise ValueError("invalid requirement group minimum")
        values = []
        for row in members:
            got = by_id.get(row["skill_id"])
            value = float(got is not None) if side == "bonus" else cover_required(
                (got or {}).get("proficiency"), row.get("proficiency"), got is not None)
            values.append({**row, "name": row.get("name") or row["skill_id"],
                           "excerpt": row.get("excerpt") or "", "cover": value,
                           "category": row.get("category_id") or row.get("category"),
                           "required_proficiency": row.get("proficiency"),
                           "resume_proficiency": (got or {}).get("proficiency")})
        selected = sorted(values, key=lambda row: (-row["cover"], row["skill_id"]))[:minimum]
        value = sum(row["cover"] for row in selected)
        totals[side] += minimum
        covers[side] += value
        ledger.extend({**row, "side": side, "counted": row in selected} for row in values)
        covered.extend(row for row in values if row["cover"] == 1)
        if side == "required" and value < minimum:
            missing = [row for row in selected if row["cover"] < 1]
            half.extend(row for row in missing if row["cover"] == 0.5)
            if members[0].get("group_id"):
                gaps.append({**missing[0], "cover": value / minimum,
                             "missing_count": len(missing), "candidates": values})
            else:
                gaps.extend(missing)
            allowed.extend(row["skill_id"] for row in values if row["cover"] < 1)
            shift_items.extend({**row, "id": row["skill_id"], "delta": 1 - row["cover"]} for row in missing)
    scoring = dict(req_cover=covers["required"], bonus_cover=covers["bonus"],
                   req_full=totals["required"], bonus_full=totals["bonus"])
    score = match_score(**scoring)
    order = shift_set(shift_items, **scoring, score=score)
    by_shift = {row["id"]: row for row in shift_items}
    # 不把被截断的集合当成已验证的换档条件。
    path = [{"skill_id": sid, "name": by_shift[sid]["name"],
             "excerpt": by_shift[sid]["excerpt"], "why": "换档", "url": ""}
            for sid in order] if len(order) <= PATH_MAX else []
    return {"score": score, "band": band_of(score), "req_cover": covers["required"],
            "req_full": totals["required"], "half": half, "gaps": gaps, "covered": covered,
            "path": path, "shift_ids": order, "allowed_skill_ids": sorted(set(allowed)),
            "ledger": ledger, "extra": [row for row in resume_skills if row.get("skill_id") not in
                                      {item["skill_id"] for item in requires}],
            "watching_copy": WATCHING_COPY}
