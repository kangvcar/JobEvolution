from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.pipeline.constants import EXTRACT_RETRY

SYSTEM_PROMPT = (
    "Extract JD JSON. Fields: job_name, domain, skills. "
    "domain must be one of: ai, data, system, iot. "
    "Each skill: name, kind, proficiency, confidence, excerpt, section. "
    "kind must be required or bonus. "
    "proficiency must be aware, able, or expert. "
    "section must be duty, requirement, benefit, or intro. "
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


class ExtractedSkill(BaseModel):
    name: str
    kind: Literal["required", "bonus"]
    proficiency: Literal["aware", "able", "expert"]
    confidence: float = Field(ge=0, le=1)
    excerpt: str = ""
    section: Literal["duty", "requirement", "benefit", "intro"] = "requirement"


class ExtractedJd(BaseModel):
    job_name: str = Field(min_length=1)
    domain: str = "ai"
    skills: list[ExtractedSkill] = Field(default_factory=list)


EXTRACT_SCHEMA = ExtractedJd.model_json_schema()


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
        return {"job_name": "", "domain": "ai", "skills": []}
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
            }
        )
    domain = _alias(_DOMAIN, payload.get("domain"), "ai")
    return {
        "job_name": str(payload.get("job_name") or "").strip(),
        "domain": domain,
        "skills": skills,
    }


def extract_messages(snapshot: dict | None) -> list[dict]:
    snap = snapshot or {}
    return [
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


def parse_extracted(complete_json, retry: bool = True, messages=None, snapshot=None) -> ExtractedJd:
    if messages is None:
        messages = extract_messages(snapshot)
    attempts = (EXTRACT_RETRY + 1) if retry else 1
    last: Exception | None = None
    for _ in range(attempts):
        try:
            payload = complete_json(EXTRACT_SCHEMA, messages)
            return ExtractedJd.model_validate(coerce_extracted(payload))
        except Exception as exc:
            last = exc
    raise ValueError("extract json failed") from last
