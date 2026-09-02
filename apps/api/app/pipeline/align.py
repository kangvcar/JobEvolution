from __future__ import annotations

import re
import unicodedata

from app.llm.embed import cosine, embed
from app.pipeline.constants import ALIGN_THRESHOLD, JOB_ALIGN_THRESHOLD
from app.targets import JOB_TARGET_NAMES


_SPACE = re.compile(r"\s+")
_PUNCT = str.maketrans({"，": ",", "。": ".", "：": ":", "；": ";", "（": "(", "）": ")", "／": "/"})
APPROVED_SYNONYMS = {"prompt engineering": "提示词工程", "提示词工程": "prompt engineering"}
FORBIDDEN_PAIRS = frozenset(
    frozenset(pair)
    for pair in (("langchain", "langgraph"), ("gpt", "gemini"), ("rag", "向量数据库"), ("pytorch", "tensorflow"))
)


def normalize_surface(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).translate(_PUNCT)
    return _SPACE.sub(" ", value.strip()).casefold()


def _approved_forms(skill: dict) -> set[str]:
    names = [skill.get("name") or "", *(skill.get("synonyms") or [])]
    forms = {normalize_surface(name) for name in names if name}
    for form, canonical in APPROVED_SYNONYMS.items():
        if form in forms:
            forms.add(normalize_surface(canonical))
    return forms


def _pair_forbidden(left: str, right: str) -> bool:
    return frozenset((normalize_surface(left), normalize_surface(right))) in FORBIDDEN_PAIRS


def _exact_hit(text: str, index: list[dict]) -> bool:
    needle = normalize_surface(text)
    if not needle:
        return False
    for skill in index:
        if needle in _approved_forms(skill):
            return True
    return False


def split_composite(name: str, index: list[dict]) -> list[str]:
    """并列串写（C/C++、Linux/Windows）只在每个部分都能精确命中词表时才拆，否则原样返回。"""
    if "/" not in (name or ""):
        return [name]
    parts = [p.strip() for p in name.split("/") if p.strip()]
    if len(parts) > 1 and all(_exact_hit(p, index) for p in parts):
        return parts
    return [name]


def align_skill(
    text: str,
    index: list[dict],
    embed_fn=embed,
    threshold: float | None = None,
    allow_embedding: bool = True,
) -> dict | None:
    needle = normalize_surface(text)
    if not needle:
        return None
    cut = ALIGN_THRESHOLD if threshold is None else float(threshold)
    for skill in index:
        if needle in _approved_forms(skill):
            return skill
    if not allow_embedding:
        return None
    query = embed_fn([text])[0]
    best = None
    best_score = -1.0
    for skill in index:
        vec = skill.get("embedding")
        if not vec:
            continue
        if _pair_forbidden(text, skill.get("name") or ""):
            continue
        score = cosine(query, vec)
        if score > best_score:
            best, best_score = skill, score
    if best is not None and best_score >= cut:
        return best
    return None


def nearest_skill(text: str, index: list[dict], embed_fn=embed) -> tuple[dict | None, float]:
    """Return a semantic neighbour for a review proposal, never for auto-alignment."""
    query = embed_fn([text])[0]
    best = None
    best_score = -1.0
    for skill in index:
        vec = skill.get("embedding")
        if not vec or _pair_forbidden(text, skill.get("name") or ""):
            continue
        score = cosine(query, vec)
        if score > best_score:
            best, best_score = skill, score
    return best, best_score


def align_job(name: str, embed_fn=embed) -> str | None:
    text = (name or "").strip()
    if not text:
        return None
    for target in JOB_TARGET_NAMES:
        if text.casefold() == target.casefold():
            return target
    query = embed_fn([text])[0]
    targets = embed_fn(list(JOB_TARGET_NAMES))
    best_i = -1
    best = -1.0
    for i, vec in enumerate(targets):
        score = cosine(query, vec)
        if score > best:
            best_i, best = i, score
    if best_i >= 0 and best >= JOB_ALIGN_THRESHOLD:
        return JOB_TARGET_NAMES[best_i]
    return None


def cluster_texts(texts: list[str], embed_fn=embed) -> list[list[str]]:
    if not texts:
        return []
    vecs = embed_fn(texts)
    used = [False] * len(texts)
    clusters: list[list[str]] = []
    for i, name in enumerate(texts):
        if used[i]:
            continue
        group = [name]
        used[i] = True
        for j in range(i + 1, len(texts)):
            if used[j]:
                continue
            if cosine(vecs[i], vecs[j]) >= ALIGN_THRESHOLD:
                group.append(texts[j])
                used[j] = True
        clusters.append(group)
    return clusters


def surface_clusters(texts: list[str]) -> list[list[str]]:
    """Group only spelling variants. Semantic merges require a review proposal."""
    groups: dict[str, list[str]] = {}
    for text in texts:
        groups.setdefault(normalize_surface(text), []).append(text)
    return list(groups.values())
