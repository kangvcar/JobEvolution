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
    if not resume_prof or not job_prof:
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
        return []
    selected = []
    for row in sorted(items, key=lambda item: (-item["delta"], item["id"])):
        if row["id"] in selected:
            continue
        selected.append(row["id"])
        req_cover += row["delta"]
        if match_score(req_cover=req_cover, bonus_cover=bonus_cover,
                       req_full=req_full, bonus_full=bonus_full) + 1e-9 >= target * 100:
            return selected
    return []
