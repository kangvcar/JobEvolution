"""Redis fingerprint set and jobs:events stream."""

from __future__ import annotations

import json
import os

FP_KEY = "ingest:fp"
STREAM_KEY = "jobs:events"
EVENT_JD_INGESTED = "jd_ingested"


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
