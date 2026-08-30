"""Redis fingerprint set and jobs:events stream."""

from __future__ import annotations

import json
import os
from collections import defaultdict

FP_KEY = "ingest:fp"
STREAM_KEY = "jobs:events"
EVENT_JD_INGESTED = "jd_ingested"


class MemoryRedis:
    """In-process stand-in so pytest does not need docker Redis."""

    def __init__(self):
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._streams: dict[str, list[tuple[str, dict[str, str]]]] = defaultdict(list)
        self._seq = 0

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    def sadd(self, key: str, *values: str) -> int:
        bucket = self._sets[key]
        added = 0
        for value in values:
            if value not in bucket:
                bucket.add(value)
                added += 1
        return added

    def xadd(self, name: str, fields: dict, id: str = "*") -> str:
        self._seq += 1
        entry_id = f"0-{self._seq}" if id == "*" else id
        self._streams[name].append((entry_id, {str(k): str(v) for k, v in fields.items()}))
        return entry_id

    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None):
        items = list(self._streams.get(name, []))
        if count is not None:
            items = items[:count]
        return items


def connect_redis(url: str | None = None):
    import redis

    return redis.Redis.from_url(
        url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


def emit_jd_ingested(client, snapshot: dict) -> str:
    payload = {
        "path": snapshot["path"],
        "domain": snapshot["domain"],
        "company": snapshot["company"],
        "title": snapshot["title"],
        "fingerprint": snapshot["fingerprint"],
        "simhash": snapshot["simhash"],
        "observed_at": snapshot.get("observed_at") or "",
    }
    return client.xadd(
        STREAM_KEY,
        {
            "id": snapshot["id"],
            "type": EVENT_JD_INGESTED,
            "payload": json.dumps(payload, ensure_ascii=False),
        },
    )
