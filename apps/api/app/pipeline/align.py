from __future__ import annotations

from app.llm.embed import cosine, embed
from app.pipeline.constants import ALIGN_THRESHOLD, JOB_ALIGN_THRESHOLD
from app.targets import JOB_TARGET_NAMES


def _exact_hit(text: str, index: list[dict]) -> bool:
    needle = (text or "").strip().casefold()
    if not needle:
        return False
    for skill in index:
        names = [skill.get("name") or "", *(skill.get("synonyms") or [])]
        if needle in {n.strip().casefold() for n in names if n}:
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
) -> dict | None:
    needle = (text or "").strip().casefold()
    if not needle:
        return None
    cut = ALIGN_THRESHOLD if threshold is None else float(threshold)
    for skill in index:
        names = [skill.get("name") or "", *(skill.get("synonyms") or [])]
        if needle in {n.strip().casefold() for n in names if n}:
            return skill
    query = embed_fn([text])[0]
    best = None
    best_score = -1.0
    for skill in index:
        vec = skill.get("embedding")
        if not vec:
            continue
        score = cosine(query, vec)
        if score > best_score:
            best, best_score = skill, score
    if best is not None and best_score >= cut:
        return best
    return None


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
