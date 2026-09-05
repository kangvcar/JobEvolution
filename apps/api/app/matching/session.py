from __future__ import annotations

import json
import os
import time
import uuid

from app.collectors.sink import connect_redis

TTL = 3600
PREFIX = "session:"

_mem: dict[str, tuple[float, str]] = {}


def _redis(key: str = ""):
    is_session = key.startswith(PREFIX)
    try:
        client = connect_redis(os.environ.get("SESSION_REDIS_URL") if is_session else None)
        client.ping()
        return client
    except Exception:
        # 会话丢了用户会直接感知，必须报错；其他键只是查询缓存，Redis 不在就退回进程内存。
        if is_session and os.environ.get("NEO4J_TEST") != "1":
            raise RuntimeError("临时存储不可用，请稍后重试")
        return None


def cache_get(key: str) -> str | None:
    if not key:
        return None
    client = _redis(key)
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
    client = _redis(key)
    if client is not None:
        client.set(key, value, ex=ttl)
        return
    _mem[key] = (time.time() + ttl, value)


def save(payload: dict) -> str:
    sid = uuid.uuid4().hex
    payload = {**payload, "expires_at": time.time() + TTL}
    cache_set(PREFIX + sid, json.dumps(payload, ensure_ascii=False), TTL)
    return sid


def load(sid: str) -> dict | None:
    raw = cache_get(PREFIX + sid) if sid else None
    payload = json.loads(raw) if raw else None
    return payload if payload and payload.get("expires_at", 0) > time.time() else None


def update(sid: str, payload: dict) -> bool:
    original = load(sid)
    if original is None:
        return False
    remaining = int(original["expires_at"] - time.time())
    if remaining <= 0:
        return False
    payload = {**payload, "expires_at": original["expires_at"]}
    cache_set(PREFIX + sid, json.dumps(payload, ensure_ascii=False), remaining)
    return True
