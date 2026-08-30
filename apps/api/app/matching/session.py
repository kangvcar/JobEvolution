from __future__ import annotations

import json
import time
import uuid

from app.collectors.sink import connect_redis

TTL = 3600
PREFIX = "session:"

_mem: dict[str, tuple[float, object]] = {}


def _redis():
    try:
        client = connect_redis()
        client.ping()
        return client
    except Exception:
        return None


def save(payload: dict) -> str:
    sid = uuid.uuid4().hex
    raw = json.dumps(payload, ensure_ascii=False)
    client = _redis()
    if client is not None:
        client.set(PREFIX + sid, raw, ex=TTL)
    else:
        _mem[sid] = (time.time() + TTL, payload)
    return sid


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
    value = row[1]
    return value if isinstance(value, str) else None


def cache_set(key: str, value: str, ttl: int) -> None:
    if not key:
        return
    client = _redis()
    if client is not None:
        client.set(key, value, ex=ttl)
        return
    _mem[key] = (time.time() + ttl, value)


def load(sid: str) -> dict | None:
    if not sid:
        return None
    client = _redis()
    if client is not None:
        raw = client.get(PREFIX + sid)
        if not raw:
            return None
        return json.loads(raw)
    row = _mem.get(sid)
    if row is None or row[0] < time.time():
        _mem.pop(sid, None)
        return None
    return row[1]
