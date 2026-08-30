"""Local embeddings. Not a DeepSeek call."""

from __future__ import annotations

import hashlib
import math

_DIM = 64


def _ngram_vec(text: str) -> list[float]:
    # ponytail: char 3-gram hash embed, swap for BAAI/bge-m3 when eval F1 needs it
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


def embed(texts: list[str]) -> list[list[float]]:
    return [_ngram_vec(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
