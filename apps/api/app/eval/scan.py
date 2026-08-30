from __future__ import annotations

from app.eval.freeze import align_threshold
from app.matching.resume import _name_in_text
from app.pipeline.align import align_skill
from app.pipeline.sections import split_sections


def duty_text(body: str) -> str:
    parts = split_sections(body or "")
    return (parts.get("duty") or "") + "\n" + (parts.get("requirement") or "")


def mention_skill_ids(text: str, index: list[dict], threshold: float | None = None) -> list[dict]:
    # ponytail: vocab scan is the annotator stand-in; swap for LLM extract if contest F1 is vs 管线抽出
    """Graph vocab names/synonyms found in text, then align_skill at freeze threshold."""
    cut = align_threshold() if threshold is None else float(threshold)
    blob = (text or "").casefold()
    found = []
    seen: set[str] = set()
    for skill in index:
        names = [skill.get("name") or "", *(skill.get("synonyms") or [])]
        hit_name = next((n for n in names if n and _name_in_text(n, blob)), None)
        if not hit_name:
            continue
        hit = align_skill(hit_name, index, threshold=cut)
        if hit is None or hit["id"] in seen:
            continue
        seen.add(hit["id"])
        found.append(
            {
                "id": hit["id"],
                "name": hit.get("name") or hit_name,
                "kind": "required",
                "proficiency": None,
            }
        )
    return found


def skill_ids(rows: list[dict]) -> set[str]:
    out = set()
    for row in rows:
        sid = row.get("id") or row.get("skill_id")
        if sid:
            out.add(sid)
    return out
