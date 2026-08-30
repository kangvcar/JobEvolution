from __future__ import annotations

BANDS = (
    (0.85, "高度匹配"),
    (0.60, "基本匹配"),
    (0.35, "有明显差距"),
    (0.0, "不匹配"),
)

PROF_RANK = {"aware": 1, "able": 2, "expert": 3}
PATH_MAX = 5


def band_of(score: float) -> str:
    ratio = score / 100.0
    for cut, label in BANDS:
        if ratio >= cut:
            return label
    return "不匹配"


def next_cut(score: float) -> float | None:
    ratio = score / 100.0
    cuts = sorted({cut for cut, _ in BANDS if cut > 0})
    for cut in cuts:
        if ratio < cut:
            return cut
    return None


def match_score(*, req_cover: float, bonus_cover: float, req_full: float, bonus_full: float) -> float:
    denom = req_full + 0.3 * bonus_full
    if denom <= 0:
        return 0.0
    return 100.0 * (req_cover + 0.3 * bonus_cover) / denom


def cover_required(resume_prof: str | None, job_prof: str | None, aligned: bool) -> float:
    if not aligned:
        return 0.0
    if not resume_prof:
        return 1.0
    need = PROF_RANK.get(job_prof or "able", 2)
    have = PROF_RANK.get(resume_prof, 2)
    if have < need:
        return 0.5
    return 1.0


def shift_set(
    items: list[dict],
    *,
    req_cover: float,
    bonus_cover: float,
    req_full: float,
    bonus_full: float,
    score: float,
) -> list[str]:
    """items: {id, delta} for gaps (1.0) and half-bands (0.5)."""
    target = next_cut(score)
    if target is None:
        return [row["id"] for row in items]
    singles: list[dict] = []
    rest: list[dict] = []
    for row in items:
        lifted = match_score(
            req_cover=req_cover + row["delta"],
            bonus_cover=bonus_cover,
            req_full=req_full,
            bonus_full=bonus_full,
        )
        if lifted / 100.0 >= target:
            singles.append(row)
        else:
            rest.append(row)
    ordered = list(singles)
    used: set[str] = set()
    for i, left in enumerate(rest):
        if left["id"] in used:
            continue
        paired = False
        for right in rest[i + 1 :]:
            if right["id"] in used:
                continue
            lifted = match_score(
                req_cover=req_cover + left["delta"] + right["delta"],
                bonus_cover=bonus_cover,
                req_full=req_full,
                bonus_full=bonus_full,
            )
            if lifted / 100.0 >= target:
                ordered.extend([left, right])
                used.add(left["id"])
                used.add(right["id"])
                paired = True
                break
        if not paired and left["id"] not in used:
            continue
    leftover = [row for row in rest if row["id"] not in used]
    ordered.extend(leftover)
    return [row["id"] for row in ordered]
