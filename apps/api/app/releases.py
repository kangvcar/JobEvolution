"""发布快照和请求读取上下文。后台仍编辑工作图，公开请求只读发布 JSON。"""
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json
import fcntl
import os
from pathlib import Path

view = ContextVar("graph_release_view", default=None)
writing = ContextVar("graph_writing", default=False)


def write_guard(fn):
    @wraps(fn)
    def write(*args, **kwargs):
        if writing.get():
            return fn(*args, **kwargs)
        path = Path(os.environ.get("DATA_DIR", "/tmp")) / ".graph-write.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: 单服务器共享文件锁串行化写图；多服务器时改数据库事务锁。
        with path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            token = writing.set(True)
            try:
                return fn(*args, **kwargs)
            finally:
                writing.reset(token)
    return write

GLOBAL_READS = ("list_domains", "list_skills", "list_jobs", "discover_boards", "build_feed")
JOB_READS = ("get_public_job", "get_any_job", "list_requires", "list_requires_history",
             "current_definition", "list_job_evidence", "list_job_events", "discover_dossier", "diagnostic_release")


def snapshot_read(fn):
    @wraps(fn)
    def read(*args, **kwargs):
        snapshot = view.get()
        if snapshot is None:
            return fn(*args, **kwargs)
        name = fn.__name__
        if name in JOB_READS:
            value = snapshot[name].get(args[0] if args else kwargs["job_id"])
            if value is None and name not in {"get_public_job", "get_any_job", "discover_dossier"}:
                value = {"ok": False, "errors": []} if name == "diagnostic_release" else []
        else:
            value = snapshot[name]
        value = deepcopy(value)
        if name == "list_jobs":
            for field in ("domain", "status"):
                if kwargs.get(field):
                    value = [row for row in value if row.get(field) == kwargs[field]]
            if kwargs.get("q"):
                value = [row for row in value if kwargs["q"].casefold() in row.get("name", "").casefold()]
            if kwargs.get("category") or kwargs.get("level"):
                value = [row for row in value if any(
                    (not kwargs.get("category") or edge.get("category_id") == kwargs["category"])
                    and (not kwargs.get("level") or kwargs["level"] in (edge.get("levels") or []))
                    for edge in snapshot["list_requires"].get(row["id"], []))]
        if name == "list_skills" and kwargs.get("with_embed") is False:
            for row in value:
                row.pop("embedding", None)
        if name == "list_job_evidence" and not kwargs.get("include_retracted"):
            value = [row for row in value if not row.get("retracted")]
        return value
    return read


def capture() -> dict:
    from app import graph
    data = {name: getattr(graph, name)(domain=None, status=None, q=None) if name == "list_jobs"
            else getattr(graph, name)() for name in GLOBAL_READS}
    with graph._driver.session() as session:
        ids = [row["id"] for row in session.run("MATCH (j:Job) RETURN j.id AS id")]
    for name in JOB_READS:
        data[name] = {jid: getattr(graph, name)(jid, **({"include_retracted": True} if name == "list_job_evidence" else {}))
                      for jid in ids}
    return data


def load(release_id: str | None = None) -> dict | None:
    from app import graph
    with graph._driver.session() as session:
        row = session.run(
            "MATCH (p:GraphPointer {id:'public'}) MATCH (r:GraphRelease) "
            "WHERE r.id = coalesce($id,p.release_id) RETURN r.snapshot AS snapshot",
            id=release_id).single()
    return json.loads(row["snapshot"]) if row and row["snapshot"] else None
