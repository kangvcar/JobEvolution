from __future__ import annotations

import json
import time
import uuid

from app.collectors.sink import connect_redis

TTL = 3600
PREFIX = "session:"

_mem: dict[str, tuple[float, str]] = {}


def _redis():
    try:
        client = connect_redis()
        client.ping()
        return client
    except Exception:
        return None


def cache_get(key: str) -> str | None:
    if not key:
        return None
    client = _redis()
    if client is not None:
        raw = client.get(key)
        return raw if isinstance(raw, str) else None
    row = _mem.get(key)
    if row is None or row[0] < time.time():
        _mem.pop(key, None)
        return None
    return row[1]


def cache_set(key: str, value: str, ttl: int) -> None:
    if not key:
        return
    client = _redis()
    if client is not None:
        client.set(key, value, ex=ttl)
        return
    _mem[key] = (time.time() + ttl, value)


def save(payload: dict) -> str:
    sid = uuid.uuid4().hex
    cache_set(PREFIX + sid, json.dumps(payload, ensure_ascii=False), TTL)
    return sid


def load(sid: str) -> dict | None:
    raw = cache_get(PREFIX + sid) if sid else None
    return json.loads(raw) if raw else None


def update(sid: str, payload: dict) -> bool:
    if not sid or cache_get(PREFIX + sid) is None:
        return False
    cache_set(PREFIX + sid, json.dumps(payload, ensure_ascii=False), TTL)
    return True
