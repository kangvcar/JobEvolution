from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedSkill(BaseModel):
    name: str
    kind: Literal["required", "bonus"]
    proficiency: Literal["aware", "able", "expert"]
    confidence: float = Field(ge=0, le=1)
    excerpt: str = ""
    section: Literal["duty", "requirement", "benefit", "intro"] = "requirement"


class ExtractedJd(BaseModel):
    job_name: str
    domain: str = "ai"
    skills: list[ExtractedSkill] = Field(default_factory=list)


EXTRACT_SCHEMA = ExtractedJd.model_json_schema()


def parse_extracted(complete_json, retry: bool = True, messages=None, snapshot=None) -> ExtractedJd:
    if messages is None:
        snap = snapshot or {}
        messages = [
            {
                "role": "system",
                "content": "Extract the job name, domain, and skills as JSON. Skills only from duties/requirements. Each skill needs kind, proficiency, confidence 0-1, excerpt, section.",
            },
            {
                "role": "user",
                "content": (
                    f"title: {snap.get('title') or ''}\n"
                    f"domain: {snap.get('domain') or ''}\n"
                    f"body:\n{snap.get('body') or ''}"
                ),
            },
        ]
    attempts = 2 if retry else 1
    last: Exception | None = None
    for _ in range(attempts):
        try:
            payload = complete_json(EXTRACT_SCHEMA, messages)
            return ExtractedJd.model_validate(payload)
        except Exception as exc:
            last = exc
    raise ValueError("extract json failed") from last
