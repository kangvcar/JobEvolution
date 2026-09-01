from __future__ import annotations

import json

from app.eval.paths import eval_dir

_cache: dict | None = None


def load_freeze() -> dict:
    """Eval reads only data/eval/freeze.json. Never ALIGN_THRESHOLD from the environment."""
    global _cache
    if _cache is not None:
        return _cache
    path = eval_dir() / "freeze.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache = {
        "align_threshold": float(data["align_threshold"]),
        "model": data.get("model") or "",
        "date": data.get("date") or "",
        "path": str(path),
    }
    return _cache


def align_threshold() -> float:
    return load_freeze()["align_threshold"]


def freeze_hash() -> str:
    import hashlib

    raw = (eval_dir() / "freeze.json").read_bytes()
    return hashlib.sha256(raw).hexdigest()
