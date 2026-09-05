"""发布快照和请求读取上下文。后台仍编辑工作图，公开请求只读发布 JSON。"""
from collections import OrderedDict
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json
import fcntl
import os
from pathlib import Path
import threading

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
        if name == "list_skills":
            # 技能向量占快照大头，整表 deepcopy 一次要上秒；不要向量时先剔掉，要向量时只拷行、向量只读共享。
            keep_embed = kwargs.get("with_embed", True)
            value = [{k: (v if k == "embedding" else deepcopy(v)) for k, v in row.items() if keep_embed or k != "embedding"}
                     for row in value]
        else:
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


# 快照 JSON 有几十 MB（技能向量占大头），每个请求都拉一遍再 json.loads 要 2~3 秒，并发几个请求就把线程池和
# Neo4j 连接一起拖死。release 一经发布不可变（MERGE ... ON CREATE SET），按 id 缓存解析结果即可；
# 指针切换、回滚只是换 id，天然失效。留两份是为了让绑定旧版本的诊断会话不和公开版本互相挤出。
_CACHE_LIMIT = 2
_cache: "OrderedDict[str, dict]" = OrderedDict()
_cache_lock = threading.Lock()


def _resolve_release_id(release_id: str | None) -> str | None:
    from app import graph
    with graph._driver.session() as session:
        row = session.run(
            "MATCH (p:GraphPointer {id:'public'}) RETURN coalesce($id, p.release_id) AS id",
            id=release_id).single()
    return row["id"] if row else None


def load(release_id: str | None = None) -> dict | None:
    from app import graph
    rid = _resolve_release_id(release_id)
    if rid is None:
        return None
    cached = _cache.get(rid)
    if cached is not None:
        return cached
    with _cache_lock:
        cached = _cache.get(rid)
        if cached is not None:
            return cached
        with graph._driver.session() as session:
            row = session.run("MATCH (r:GraphRelease {id: $id}) RETURN r.snapshot AS snapshot", id=rid).single()
        snapshot = json.loads(row["snapshot"]) if row and row["snapshot"] else None
        if snapshot is not None:
            _cache[rid] = snapshot
            while len(_cache) > _CACHE_LIMIT:
                _cache.popitem(last=False)
        return snapshot
