"""Redis fingerprint set and jobs:events stream."""

from __future__ import annotations

import json
import os

FP_KEY = "ingest:fp"
BODY_KEY = "ingest:body"
STREAM_KEY = "jobs:events"
EVENT_JD_INGESTED = "jd_ingested"
EVENT_COLLECT_STARTED = "collect_started"
EVENT_COLLECT_PORTAL_FAILED = "collect_portal_failed"
EVENT_COLLECT_FINISHED = "collect_finished"
STREAM_MAXLEN = 8000
COLLECT_EVENT_TYPES = frozenset(
    {
        EVENT_COLLECT_STARTED,
        EVENT_JD_INGESTED,
        EVENT_COLLECT_PORTAL_FAILED,
        EVENT_COLLECT_FINISHED,
    }
)


def connect_redis(url: str | None = None):
    import redis

    return redis.Redis.from_url(
        url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


def _xadd(client, event_type: str, event_id: str, payload: dict) -> str:
    try:
        return client.xadd(
            STREAM_KEY,
            {
                "id": event_id,
                "type": event_type,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
    except TypeError:
        return client.xadd(
            STREAM_KEY,
            {
                "id": event_id,
                "type": event_type,
                "payload": json.dumps(payload, ensure_ascii=False),
            },
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
        "channel": snapshot.get("channel") or "",
    }
    return _xadd(client, EVENT_JD_INGESTED, snapshot["id"], payload)


def emit_collect_event(client, event_type: str, payload: dict) -> str:
    return _xadd(client, event_type, event_type, payload)
