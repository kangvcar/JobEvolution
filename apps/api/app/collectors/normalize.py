"""Company 规范化 and ingest fingerprints."""

from __future__ import annotations

import hashlib
import re

_PAREN = re.compile(r"[（(][^）)]*[）)]")
_SPACE = re.compile(r"\s+")
# Longer legal suffixes first so 「股份有限公司」 does not stop at 「有限公司」.
_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "股份公司",
    "股份",
)

# Channel names never count as 独立源, even if they leak into company.
CHANNEL_NAMES = frozenset({"ats", "greenhouse", "lever", "ashby"})


def squash(value: str) -> str:
    return _SPACE.sub("", (value or "").strip())


def normalize_company(name: str) -> str:
    text = squash(_PAREN.sub("", name or ""))
    changed = True
    while changed and text:
        changed = False
        for suffix in _SUFFIXES:
            if text.endswith(suffix) and len(text) > len(suffix):
                text = text[: -len(suffix)]
                changed = True
                break
    return text


def is_channel_name(name: str) -> bool:
    raw = squash(name)
    if not raw:
        return False
    lowered = raw.lower()
    return raw in CHANNEL_NAMES or lowered in CHANNEL_NAMES


def fingerprint_for(
    source: str,
    job_id: str,
    company: str,
    title: str,
    city: str,
) -> str:
    if job_id:
        material = f"{source}{job_id}"
    else:
        material = f"{normalize_company(company)}|{squash(title)}|{squash(city)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
