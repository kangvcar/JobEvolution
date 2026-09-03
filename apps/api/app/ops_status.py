from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

PATH = Path(os.environ.get("OPS_STATUS_PATH", "/tmp/jobevolution-ops.json"))


def read() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pipeline": {"status": "unknown"}, "backup": {"status": "unknown"}, "publish": {"status": "unknown"}}


def record(kind: str, status: str, **extra) -> dict:
    state = read()
    state[kind] = {"status": status, "at": time.time(), **extra}
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    if status == "failed":
        hook = os.environ.get("OPS_WEBHOOK_URL")
        if hook:
            try:
                urlopen(Request(hook, data=json.dumps({"kind": kind, **state[kind]}).encode(), headers={"Content-Type": "application/json"}), timeout=5).close()
            except OSError:
                pass
    return state


def stale() -> bool:
    pipeline = read().get("pipeline", {})
    at = pipeline.get("at", 0)
    return pipeline.get("status") == "failed" or not at or time.time() - at > 48 * 3600
