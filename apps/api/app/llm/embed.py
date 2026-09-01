"""Embeddings. SiliconFlow bge-m3 when EMBED_API_KEY is set, hash fallback otherwise."""

from __future__ import annotations

import hashlib
import math
import os

_DIM = 64
_CHUNK = 32


def _ngram_vec(text: str) -> list[float]:
    # ponytail: char 3-gram hash embed，只认词面；配 EMBED_API_KEY 走远端 bge-m3，断网/欠费直接抛不降级
    vec = [0.0] * _DIM
    s = (text or "").casefold()
    if not s:
        return vec
    padded = f"  {s}  "
    for i in range(len(padded) - 2):
        gram = padded[i : i + 3].encode("utf-8")
        idx = int.from_bytes(hashlib.blake2b(gram, digest_size=2).digest(), "little") % _DIM
        vec[idx] += 1.0
    return vec


def _remote(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ.get("EMBED_BASE_URL", "https://api.siliconflow.cn/v1"),
        api_key=os.environ["EMBED_API_KEY"],
    )
    model = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
    out: list[list[float]] = []
    for i in range(0, len(texts), _CHUNK):
        resp = client.embeddings.create(model=model, input=texts[i : i + _CHUNK])
        out.extend(item.embedding for item in resp.data)
    return out


def embed(texts: list[str]) -> list[list[float]]:
    if os.environ.get("EMBED_API_KEY"):
        return _remote(texts)
    return [_ngram_vec(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
