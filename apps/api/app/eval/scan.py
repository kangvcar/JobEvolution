from __future__ import annotations

from app.eval.freeze import align_threshold
from app.pipeline.sections import split_sections
from app.pipeline.extract import vocab_mention_skills


def duty_text(body: str) -> str:
    parts = split_sections(body or "")
    return (parts.get("duty") or "") + "\n" + (parts.get("requirement") or "")


def mention_skill_ids(text: str, index: list[dict], threshold: float | None = None) -> list[dict]:
    # ponytail: vocab scan is the annotator stand-in; production uses the same recall pass.
    cut = align_threshold() if threshold is None else float(threshold)
    return [
        {"id": row["id"], "name": row["name"], "kind": "required", "proficiency": None}
        for row in vocab_mention_skills(text, index, cut)
    ]


def skill_ids(rows: list[dict]) -> set[str]:
    out = set()
    for row in rows:
        sid = row.get("id") or row.get("skill_id")
        if sid:
            out.add(sid)
    return out
