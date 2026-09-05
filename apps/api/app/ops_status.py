from __future__ import annotations

import json
import os
import time
import fcntl
from pathlib import Path
from urllib.request import Request, urlopen

PATH = Path(os.environ.get("OPS_STATUS_PATH", str(Path(os.environ.get("DATA_DIR", "/tmp")) / "ops-status.json")))


def read() -> dict:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pipeline": {"status": "unknown"}, "backup": {"status": "unknown"}, "publish": {"status": "unknown"}}


def record(kind: str, status: str, **extra) -> dict:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATH.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read()
        previous = state.get(kind, {})
        success_at = time.time() if status == "success" else previous.get("last_success_at", previous.get("at") if previous.get("status") == "success" else None)
        state[kind] = {"status": status, "at": time.time(), "last_success_at": success_at, **extra}
        temporary = PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        temporary.replace(PATH)
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
    if pipeline.get("status") == "failed":
        return True
    at = pipeline.get("last_success_at") or (pipeline.get("at") if pipeline.get("status") == "success" else 0)
    return not at or time.time() - at > 48 * 3600
