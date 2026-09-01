"""64-bit simhash; Hamming ≤3 is a near-dup."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

_WORD = re.compile(r"[A-Za-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
NEAR_DUP_DISTANCE = 3


def _tokens(text: str) -> list[str]:
    words = [m.group(0).lower() for m in _WORD.finditer(text)]
    cjk = _CJK.findall(text)
    if len(cjk) >= 2:
        grams = ["".join(cjk[i : i + 2]) for i in range(len(cjk) - 1)]
    else:
        grams = cjk
    return words + grams


def simhash64(text: str) -> int:
    tokens = _tokens(text or "")
    if not tokens:
        return 0
    vector = [0] * 64
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()[:8]
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            if value & (1 << bit):
                vector[bit] += 1
            else:
                vector[bit] -= 1
    out = 0
    for bit in range(64):
        if vector[bit] > 0:
            out |= 1 << bit
    return out


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def format_simhash(value: int) -> str:
    return f"{value:016x}"


class SimhashIndex:
    """Banded lookup so Hamming ≤3 is not a full scan. ponytail: 4×16-bit bands, rebuild if ingest >>100k."""

    def __init__(self):
        self.distance = NEAR_DUP_DISTANCE
        self._items: list[tuple[int, object]] = []
        self._bands: list[dict[int, list[int]]] = [defaultdict(list) for _ in range(4)]

    @staticmethod
    def _bands_of(value: int) -> tuple[int, int, int, int]:
        return (
            value & 0xFFFF,
            (value >> 16) & 0xFFFF,
            (value >> 32) & 0xFFFF,
            (value >> 48) & 0xFFFF,
        )

    def add(self, value: int, meta: object) -> None:
        idx = len(self._items)
        self._items.append((value, meta))
        for band, key in enumerate(self._bands_of(value)):
            self._bands[band][key].append(idx)

    def find(self, value: int):
        seen: set[int] = set()
        for band, key in enumerate(self._bands_of(value)):
            for idx in self._bands[band].get(key, ()):
                if idx in seen:
                    continue
                seen.add(idx)
                existing, meta = self._items[idx]
                if hamming(value, existing) <= self.distance:
                    return meta
        return None
