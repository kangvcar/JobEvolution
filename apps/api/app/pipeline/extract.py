from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.pipeline.constants import SKILL_CATEGORIES
from app.targets import JOB_TARGET_NAMES

SYSTEM_PROMPT = (
    "Extract JD JSON. Fields: job_name, domain, target, skills. "
    "domain must be one of: ai, data, system, iot. "
    "target is the canonical job name from this list that the JD title matches, "
    f"or empty if none does: {'、'.join(JOB_TARGET_NAMES)}. "
    "Each skill: name, kind, proficiency, confidence, excerpt, section, category. "
    "kind must be required or bonus. "
    "proficiency must be aware, able, or expert. "
    "section must be duty, requirement, benefit, or intro. "
    "category must be one of: "
    + ", ".join(SKILL_CATEGORIES)
    + ". "
    "confidence is 0-1. excerpt is a verbatim substring of the JD. "
    "Skills only from duty/requirement. Do not invent other enum values."
)

_KIND = {
    "required": "required",
    "bonus": "bonus",
    "must": "required",
    "core": "required",
    "technical": "required",
    "skill": "required",
    "必备": "required",
    "要求": "required",
    "plus": "bonus",
    "optional": "bonus",
    "nice": "bonus",
    "加分": "bonus",
}

_PROF = {
    "aware": "aware",
    "able": "able",
    "expert": "expert",
    "beginner": "aware",
    "basic": "aware",
    "familiar": "aware",
    "了解": "aware",
    "intermediate": "able",
    "proficient": "able",
    "熟练": "able",
    "advanced": "expert",
    "master": "expert",
    "精通": "expert",
}

_SECTION = {
    "duty": "duty",
    "duties": "duty",
    "responsibility": "duty",
    "responsibilities": "duty",
    "职责": "duty",
    "requirement": "requirement",
    "requirements": "requirement",
    "任职": "requirement",
    "benefit": "benefit",
    "benefits": "benefit",
    "welfare": "benefit",
    "福利": "benefit",
    "intro": "intro",
    "company": "intro",
    "介绍": "intro",
}

_DOMAIN = {
    "ai": "ai",
    "data": "data",
    "system": "system",
    "iot": "iot",
    "人工智能": "ai",
    "大数据": "data",
    "智能系统": "system",
    "物联网": "iot",
}

_CATEGORY = {cid: cid for cid in SKILL_CATEGORIES}
_CATEGORY.update(
    {
        "语言": "language",
        "框架": "framework",
        "平台": "platform",
        "工程": "engineering",
        "领域": "domain",
        "领域知识": "domain",
    }
)

_TARGETS = {name.casefold(): name for name in JOB_TARGET_NAMES}


class ExtractedSkill(BaseModel):
    name: str
    kind: Literal["required", "bonus"]
    proficiency: Literal["aware", "able", "expert"]
    confidence: float = Field(ge=0, le=1)
    excerpt: str = ""
    section: Literal["duty", "requirement", "benefit", "intro"] = "requirement"
    category: Literal["", "language", "framework", "platform", "engineering", "domain"] = ""


class ExtractedJd(BaseModel):
    job_name: str = Field(min_length=1)
    domain: str = "ai"
    target: str = ""
    skills: list[ExtractedSkill] = Field(default_factory=list)


def _alias(table: dict[str, str], value, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    folded = text.casefold()
    if folded in table:
        return table[folded]
    if text in table:
        return table[text]
    return default


def _confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if number > 1:
        number = number / 100.0
    return min(1.0, max(0.0, number))


def coerce_extracted(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"job_name": "", "domain": "ai", "target": "", "skills": []}
    skills = []
    for raw in payload.get("skills") or []:
        if isinstance(raw, str):
            raw = {"name": raw}
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        skills.append(
            {
                "name": name,
                "kind": _alias(_KIND, raw.get("kind"), "required"),
                "proficiency": _alias(_PROF, raw.get("proficiency"), "able"),
                "confidence": _confidence(raw.get("confidence")),
                "excerpt": str(raw.get("excerpt") or "").strip(),
                "section": _alias(_SECTION, raw.get("section"), "requirement"),
                "category": _alias(_CATEGORY, raw.get("category"), ""),
            }
        )
    domain = _alias(_DOMAIN, payload.get("domain"), "ai")
    target = _TARGETS.get(str(payload.get("target") or "").strip().casefold(), "")
    return {
        "job_name": str(payload.get("job_name") or "").strip(),
        "domain": domain,
        "target": target,
        "skills": skills,
    }


def parse_extracted(complete_json, snapshot: dict | None = None) -> ExtractedJd:
    snap = snapshot or {}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"title: {snap.get('title') or ''}\n"
                f"domain: {snap.get('domain') or ''}\n"
                f"body:\n{snap.get('body') or ''}"
            ),
        },
    ]
    try:
        payload = complete_json(messages)
    except Exception as exc:
        raise ValueError("extract json failed") from exc
    return ExtractedJd.model_validate(coerce_extracted(payload))
