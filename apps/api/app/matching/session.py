from __future__ import annotations

import json
import time
import uuid

from app.collectors.sink import connect_redis

TTL = 3600
PREFIX = "session:"

_mem: dict[str, tuple[float, dict]] = {}


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
