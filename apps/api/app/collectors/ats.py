"""Official career portals: public JSON → RawRecord."""

from __future__ import annotations

import fcntl
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from app.collectors.controller import ingest_records, parse_observed_at, write_json_atomic
from app.collectors.domain import classify_domain
from app.collectors.simhash import format_simhash, simhash64
from app.collectors.sink import (
    BODY_KEY,
    EVENT_COLLECT_FINISHED,
    EVENT_COLLECT_PORTAL_FAILED,
    EVENT_COLLECT_STARTED,
    emit_collect_event,
)
from app.collectors.source import RawRecord
from app.targets import JOB_TARGET_NAMES

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SEARCH_WORDS = (
    "大模型", "Agent", "智能体", "算法", "机器学习", "提示词", "AI", "C++",
    "嵌入式", "视觉", "机器人", "硬件", "物联网", "边缘计算",
)
FEISHU_PATHS = ("index", "experienced", "fte", "social", "recruitment", "campus")
MAX_NEW = 200
PAGE_SLEEP = 1.5
CHECKPOINT_FILE = "collect.checkpoint.json"
_INTERN = re.compile(r"实习|intern", re.I)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_HOST = re.compile(
    r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
CTX = ssl.create_default_context()

DEFAULT_PORTALS = [
    {"key": "tencent", "type": "tencent", "name": "腾讯", "enabled": True, "builtin": True},
    {"key": "bytedance", "type": "bytedance", "name": "字节跳动", "enabled": True, "builtin": True},
    {
        "key": "zhipu",
        "type": "feishu",
        "name": "智谱",
        "host": "zhipu-ai.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "minimax",
        "type": "feishu",
        "name": "MiniMax",
        "host": "vrfi1sk8a0.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "moonshot",
        "type": "feishu",
        "name": "月之暗面",
        "host": "moonshot.jobs.feishu.cn",
        "enabled": False,
        "builtin": False,
    },
    {
        "key": "nio",
        "type": "feishu",
        "name": "蔚来",
        "host": "nio.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "poizon",
        "type": "feishu",
        "name": "得物",
        "host": "poizon.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "bambulab",
        "type": "feishu",
        "name": "拓竹科技",
        "host": "bambulab.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "lixiang",
        "type": "feishu",
        "name": "理想汽车",
        "host": "li.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "xiaopeng",
        "type": "feishu",
        "name": "小鹏汽车",
        "host": "xiaopeng.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "xiaomi",
        "type": "feishu",
        "name": "小米",
        "host": "xiaomi.jobs.f.mioffice.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "unitree",
        "type": "beisen",
        "name": "宇树科技",
        "host": "unitree.zhiye.com",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "agirobot",
        "type": "feishu",
        "name": "智元AGIBOT",
        "host": "agirobot.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "arashivision",
        "type": "feishu",
        "name": "影石创新",
        "host": "arashivision.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "tsingtengms",
        "type": "feishu",
        "name": "紫光青藤",
        "host": "tsingtengms.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "asiainfo-sec",
        "type": "feishu",
        "name": "亚信安全",
        "host": "asiainfo-sec.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "lierda",
        "type": "feishu",
        "name": "利尔达科技",
        "host": "lierda.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "lg77oym6sy",
        "type": "feishu",
        "name": "美克生能源",
        "host": "lg77oym6sy.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
    {
        "key": "weikezhijia",
        "type": "feishu",
        "name": "马上消费",
        "host": "weikezhijia.jobs.feishu.cn",
        "enabled": True,
        "builtin": False,
    },
]


def portals_path(data_dir: Path) -> Path:
    return Path(data_dir) / "portals.json"


def lock_path(data_dir: Path) -> Path:
    return Path(data_dir) / "collect.lock"


def checkpoint_path(data_dir: Path) -> Path:
    return Path(data_dir) / CHECKPOINT_FILE


def _new_checkpoint(portals: list[dict]) -> dict:
    return {
        "version": 1,
        "run_id": str(time.time_ns()),
        "status": "running",
        "started_at": datetime.now().astimezone().isoformat(),
        "portals": {row.get("key") or "": {} for row in portals},
    }


def _load_checkpoint(data_dir: Path, portals: list[dict]) -> tuple[dict, bool]:
    path = checkpoint_path(data_dir)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = None
    if not isinstance(state, dict):
        return _new_checkpoint(portals), False
    failed = any(
        isinstance(value, dict) and value.get("status") == "failed"
        for value in (state.get("portals") or {}).values()
    )
    if state.get("status") != "running" and not failed:
        return _new_checkpoint(portals), False
    state.setdefault("portals", {})
    return state, True


def _flush_evidence(on_evidence) -> None:
    flush = getattr(on_evidence, "flush", None)
    if callable(flush):
        flush()


def load_portals(data_dir: Path) -> list[dict]:
    path = portals_path(data_dir)
    if not path.is_file():
        save_portals(data_dir, DEFAULT_PORTALS)
        return [dict(row) for row in DEFAULT_PORTALS]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [dict(row) for row in DEFAULT_PORTALS]
    rows = raw.get("portals") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        return [dict(row) for row in DEFAULT_PORTALS]
    return rows


def save_portals(data_dir: Path, portals: list[dict]) -> None:
    validate_portals(portals)
    path = portals_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"portals": portals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def enabled_count(portals: list[dict]) -> int:
    return sum(1 for row in portals if row.get("enabled"))


def valid_host(host: str) -> bool:
    return bool(_HOST.fullmatch((host or "").strip()))


def validate_portals(portals: list[dict]) -> None:
    if not isinstance(portals, list) or any(not isinstance(row, dict) for row in portals):
        raise ValueError("invalid portals")
    if enabled_count(portals) > 20:
        raise ValueError("at most 20 enabled portals")
    for row in portals:
        if row.get("type") in ("feishu", "beisen") and not valid_host(row.get("host") or ""):
            raise ValueError("invalid host")


def collect_busy(data_dir: Path) -> bool:
    path = lock_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return False


class CollectLock:
    def __init__(self, data_dir: Path):
        self.path = lock_path(data_dir)
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a+")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._fh.close()
            self._fh = None
            return False
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()
        self._fh = None


def strip_html(text: str) -> str:
    return _SPACE.sub(" ", _TAG.sub(" ", text or "")).strip()


def has_cjk(title: str, n: int = 2) -> bool:
    return len(_CJK.findall(title or "")) >= n


def is_intern(title: str) -> bool:
    return bool(_INTERN.search(title or ""))


def hits_target(title: str) -> bool:
    compact = (title or "").replace(" ", "")
    return any(name.replace(" ", "") in compact for name in JOB_TARGET_NAMES)


def keep_title(title: str, *, from_search: bool) -> bool:
    if not title or is_intern(title) or not has_cjk(title):
        return False
    return bool(classify_domain(title) or hits_target(title) or from_search)


def domain_for(title: str) -> str:
    return classify_domain(title) or "ai"


def portal_time(value) -> str:
    if value in (None, ""):
        return datetime.now().isoformat()
    if isinstance(value, (int, float)) or (isinstance(value, str) and str(value).isdigit()):
        stamp = int(value)
        if stamp > 10**12:
            stamp //= 1000
        try:
            return datetime.fromtimestamp(stamp).isoformat()
        except (OSError, ValueError, OverflowError):
            return datetime.now().isoformat()
    return parse_observed_at(str(value)) or datetime.now().isoformat()


def http_json(url: str, *, method: str = "GET", body=None, headers: dict | None = None, timeout: float = 25):
    hdrs = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", **(headers or {})}
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _sleep() -> None:
    time.sleep(PAGE_SLEEP)


def known_page_limit() -> int:
    """连续已知页的提前停止阈值；0 表示完整扫描。"""
    if os.environ.get("COLLECT_FULL_SCAN", "0").strip() == "1":
        return 0
    try:
        return max(0, min(20, int(os.environ.get("COLLECT_KNOWN_PAGES", "2"))))
    except (TypeError, ValueError):
        return 2


def next_stale_pages(current: int, *, checked: int, new: int, failed: int = 0) -> int:
    # ponytail: 依赖门户结果大致按更新时间排序；排序不稳定时用 COLLECT_FULL_SCAN=1。
    if checked and not new and not failed:
        return current + 1
    return 0


def fetch_tencent(http=http_json, sleep=_sleep, is_new=lambda _: True) -> list[RawRecord]:
    seen: set[str] = set()
    out: list[RawRecord] = []
    stale_limit = known_page_limit()

    def fetch_detail(post):
        jid = str(post.get("PostId") or "")
        try:
            detail = http(
                "https://careers.tencent.com/tencentcareer/api/post/ByPostId?"
                + urllib.parse.urlencode({"postId": jid, "language": "zh-cn"}),
                headers={
                    "Origin": "https://careers.tencent.com",
                    "Referer": "https://careers.tencent.com/",
                },
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            return None
        return post, (detail.get("Data") or {}) if isinstance(detail, dict) else {}

    for word in SEARCH_WORDS:
        page = 1
        stale_pages = 0
        while len(out) < MAX_NEW:
            qs = urllib.parse.urlencode(
                {"keyword": word, "pageIndex": page, "pageSize": 10, "language": "zh-cn", "area": "cn"}
            )
            data = http(
                f"https://careers.tencent.com/tencentcareer/api/post/Query?{qs}",
                headers={
                    "Origin": "https://careers.tencent.com",
                    "Referer": "https://careers.tencent.com/",
                },
            )
            posts = ((data.get("Data") or {}).get("Posts")) or []
            if not posts:
                break
            candidates = []
            for post in posts:
                title = post.get("RecruitPostName") or ""
                jid = str(post.get("PostId") or "")
                if not jid or jid in seen or not keep_title(title, from_search=True):
                    continue
                seen.add(jid)
                candidates.append(post)
            page_new = 0
            page_failed = 0
            with ThreadPoolExecutor(max_workers=min(8, len(candidates) or 1), thread_name_prefix="tencent-detail") as pool:
                details = pool.map(fetch_detail, candidates)
                for result in details:
                    if result is None:
                        page_failed += 1
                        continue
                    post, detail_row = result
                    title = post.get("RecruitPostName") or ""
                    jid = str(post.get("PostId") or "")
                    body = strip_html(
                        "\n\n".join(
                            x
                            for x in (
                                detail_row.get("Responsibility") or post.get("Responsibility") or "",
                                detail_row.get("Requirement") or "",
                            )
                            if x
                        )
                    )
                    if not body:
                        page_failed += 1
                        continue
                    row = RawRecord(
                        company="腾讯",
                        title=detail_row.get("RecruitPostName") or title,
                        body=body,
                        published_at=portal_time(detail_row.get("LastUpdateTime") or post.get("LastUpdateTime")),
                        city=detail_row.get("LocationName") or post.get("LocationName") or "",
                        channel="tencent",
                        job_id=jid,
                        source="ats",
                        domain=domain_for(title),
                        url=detail_row.get("PostURL") or post.get("PostURL") or "",
                    )
                    if is_new(row):
                        out.append(row)
                        page_new += 1
                    if len(out) >= MAX_NEW:
                        break
            stale_pages = next_stale_pages(
                stale_pages,
                checked=len(candidates),
                new=page_new,
                failed=page_failed,
            )
            if stale_limit and stale_pages >= stale_limit:
                break
            if len(posts) < 10:
                break
            page += 1
            sleep()
    return out


def fetch_bytedance(http=http_json, sleep=_sleep, is_new=lambda _: True) -> list[RawRecord]:
    seen: set[str] = set()
    out: list[RawRecord] = []
    stale_limit = known_page_limit()
    headers = {
        "portal-channel": "office",
        "portal-platform": "pc",
        "Origin": "https://jobs.bytedance.com",
        "Referer": "https://jobs.bytedance.com/experienced/position",
    }
    for word in SEARCH_WORDS:
        offset = 0
        stale_pages = 0
        while len(out) < MAX_NEW:
            data = http(
                "https://jobs.bytedance.com/api/v1/search/job/posts",
                method="POST",
                body={
                    "keyword": word,
                    "limit": 30,
                    "offset": offset,
                    "job_category_id_list": [],
                    "location_code_list": [],
                    "subject_id_list": [],
                    "recruitment_id_list": [],
                },
                headers=headers,
            )
            posts = ((data.get("data") or {}).get("job_post_list")) or []
            if not posts:
                break
            page_candidates = 0
            page_new = 0
            for post in posts:
                title = post.get("title") or ""
                jid = str(post.get("id") or "")
                if not jid or not keep_title(title, from_search=True):
                    continue
                if jid in seen:
                    page_candidates += 1
                    continue
                seen.add(jid)
                body = strip_html(
                    "\n\n".join(x for x in (post.get("description") or "", post.get("requirement") or "") if x)
                )
                if not body:
                    continue
                page_candidates += 1
                city = (post.get("city_info") or {}).get("name") or ""
                row = RawRecord(
                    company="字节跳动",
                    title=title,
                    body=body,
                    published_at=portal_time(post.get("publish_time")),
                    city=city,
                    channel="bytedance",
                    job_id=jid,
                    source="ats",
                    domain=domain_for(title),
                    url=f"https://jobs.bytedance.com/experienced/position/{jid}/detail",
                )
                if is_new(row):
                    out.append(row)
                    page_new += 1
                if len(out) >= MAX_NEW:
                    break
            stale_pages = next_stale_pages(stale_pages, checked=page_candidates, new=page_new)
            if stale_limit and stale_pages >= stale_limit:
                break
            if len(posts) < 30:
                break
            offset += 30
            sleep()
    return out


def resolve_feishu_path(host: str, http=http_json) -> str:
    body = {
        "keyword": "",
        "limit": 1,
        "offset": 0,
        "portal_type": 2,
        "job_category_id_list": [],
        "location_code_list": [],
        "subject_id_list": [],
        "recruitment_id_list": [],
        "job_function_id_list": [],
    }
    for path in FEISHU_PATHS:
        headers = {
            "Origin": f"https://{host}",
            "Referer": f"https://{host}/",
            "Portal-Channel": "office",
            "Portal-Platform": "pc",
            "website-path": path,
        }
        try:
            data = http(
                f"https://{host}/api/v1/search/job/posts",
                method="POST",
                body=body,
                headers=headers,
                timeout=3,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("code") == 0:
            return path
    return "index"


def fetch_feishu(host: str, company: str, http=http_json, sleep=_sleep, *, probe: bool = False, is_new=lambda _: True) -> list[RawRecord]:
    if not valid_host(host):
        raise ValueError("invalid host")
    path = resolve_feishu_path(host, http=http)
    words = ("",) if probe else SEARCH_WORDS
    seen: set[str] = set()
    out: list[RawRecord] = []
    stale_limit = known_page_limit()
    for word in words:
        offset = 0
        stale_pages = 0
        while len(out) < (1 if probe else MAX_NEW):
            headers = {
                "Origin": f"https://{host}",
                "Referer": f"https://{host}/",
                "Portal-Channel": "office",
                "Portal-Platform": "pc",
                "website-path": path,
            }
            data = http(
                f"https://{host}/api/v1/search/job/posts",
                method="POST",
                body={
                    "keyword": word,
                    "limit": 2 if probe else 50,
                    "offset": offset,
                    "portal_type": 2,
                    "job_category_id_list": [],
                    "location_code_list": [],
                    "subject_id_list": [],
                    "recruitment_id_list": [],
                    "job_function_id_list": [],
                },
                headers=headers,
                timeout=3 if probe else 25,
            )
            if not isinstance(data, dict) or data.get("code") not in (0, None):
                raise ValueError(f"feishu code {data.get('code') if isinstance(data, dict) else 'invalid'}")
            posts = ((data.get("data") or {}).get("job_post_list")) or []
            if not posts:
                break
            if probe:
                return [
                    RawRecord(
                        company=company,
                        title=posts[0].get("title") or "probe",
                        body="probe",
                        published_at="",
                        city="",
                        channel=host,
                        job_id=str(posts[0].get("id") or "probe"),
                        source="ats",
                    )
                ]
            from_search = bool(word)
            page_candidates = 0
            page_new = 0
            for post in posts:
                title = post.get("title") or ""
                jid = str(post.get("id") or "")
                if not jid or not keep_title(title, from_search=from_search):
                    continue
                if jid in seen:
                    page_candidates += 1
                    continue
                seen.add(jid)
                body = strip_html(
                    "\n\n".join(x for x in (post.get("description") or "", post.get("requirement") or "") if x)
                )
                if not body:
                    continue
                page_candidates += 1
                cities = ", ".join(
                    c.get("name", "") for c in (post.get("city_list") or []) if isinstance(c, dict)
                )
                row = RawRecord(
                    company=company,
                    title=title,
                    body=body,
                    published_at=portal_time(post.get("publish_time")),
                    city=cities,
                    channel=host,
                    job_id=jid,
                    source="ats",
                    domain=domain_for(title),
                    url=f"https://{host}/{path}/position/{jid}/detail",
                )
                if is_new(row):
                    out.append(row)
                    page_new += 1
                if len(out) >= MAX_NEW:
                    break
            stale_pages = next_stale_pages(stale_pages, checked=page_candidates, new=page_new)
            if stale_limit and stale_pages >= stale_limit:
                break
            if len(posts) < 50:
                break
            offset += 50
            sleep()
    return out


def fetch_beisen(host: str, company: str, http=http_json, sleep=_sleep, is_new=lambda _: True) -> list[RawRecord]:
    if not valid_host(host):
        raise ValueError("invalid host")
    page = 1
    page_size = 50
    out: list[RawRecord] = []
    stale_limit = known_page_limit()
    stale_pages = 0
    while len(out) < MAX_NEW:
        data = http(
            f"https://{host}/api/Jobad/GetJobAdPageList",
            method="POST",
            body={"pageIndex": page, "pageSize": page_size},
            headers={"Origin": f"https://{host}", "Referer": f"https://{host}/jobs"},
            timeout=25,
        )
        status = data.get("Code", data.get("code")) if isinstance(data, dict) else None
        if status not in (None, 0, 200, "200"):
            raise ValueError(f"beisen code {status}")
        posts = (data.get("Data") or []) if isinstance(data, dict) else []
        if not isinstance(posts, list) or not posts:
            break
        page_candidates = 0
        page_new = 0
        page_failed = 0
        for post in posts:
            title = post.get("JobAdName") or post.get("name") or ""
            jid = str(post.get("JobAdId") or post.get("Id") or "")
            if not jid or not keep_title(title, from_search=True):
                continue
            page_candidates += 1
            body = strip_html("\n\n".join(x for x in (post.get("Duty") or "", post.get("Require") or "") if x))
            candidate = RawRecord(
                company=company,
                title=title,
                body=body,
                published_at="",
                city="",
                channel=host,
                job_id=jid,
                source="ats",
            )
            if not body:
                page_failed += 1
                continue
            if not is_new(candidate):
                continue
            locations = post.get("LocNames") or []
            cities = ", ".join(
                (item.get("Name") or item.get("name") or "") if isinstance(item, dict) else str(item)
                for item in locations
            )
            out.append(
                RawRecord(
                    company=company,
                    title=title,
                    body=body,
                    published_at=portal_time(post.get("PostDate")),
                    city=cities,
                    channel=host,
                    job_id=jid,
                    source="ats",
                    domain=domain_for(title),
                    url=f"https://{host}/jobad/{jid}",
                )
            )
            page_new += 1
            if len(out) >= MAX_NEW:
                break
        stale_pages = next_stale_pages(
            stale_pages,
            checked=page_candidates,
            new=page_new,
            failed=page_failed,
        )
        if stale_limit and stale_pages >= stale_limit:
            break
        if len(posts) < page_size:
            break
        page += 1
        sleep()
    return out


def probe_feishu(host: str, http=http_json) -> None:
    rows = fetch_feishu(host, "probe", http=http, sleep=lambda: None, probe=True)
    if not rows:
        raise ValueError("empty list")


def fetch_portal(portal: dict, http=http_json, sleep=_sleep, is_new=lambda _: True) -> list[RawRecord]:
    kind = portal.get("type")
    if kind == "tencent":
        return fetch_tencent(http=http, sleep=sleep, is_new=is_new)
    if kind == "bytedance":
        return fetch_bytedance(http=http, sleep=sleep, is_new=is_new)
    if kind == "feishu":
        return fetch_feishu(portal.get("host") or "", portal.get("name") or portal.get("key") or "飞书", http=http, sleep=sleep, is_new=is_new)
    if kind == "beisen":
        return fetch_beisen(portal.get("host") or "", portal.get("name") or portal.get("key") or "北森", http=http, sleep=sleep, is_new=is_new)
    raise ValueError(f"unsupported type {kind}")


def run_official(*, data_dir: Path, out_dir: Path, redis, http=http_json, sleep=_sleep, on_evidence=None, workers=None) -> dict:
    portals = [row for row in load_portals(data_dir) if row.get("enabled")]
    validate_portals(portals)
    checkpoint, resumed = _load_checkpoint(data_dir, portals)
    write_json_atomic(checkpoint_path(data_dir), checkpoint)
    emit_collect_event(redis, EVENT_COLLECT_STARTED, {"portals": [row.get("key") for row in portals]})
    stats_by_key = {}
    any_ok = False
    pending = []
    worker_count = 0
    for portal in portals:
        key = portal.get("key") or ""
        previous = checkpoint.get("portals", {}).get(key) or {}
        if resumed and previous.get("status") == "done":
            stat = previous.get("stats") or {"key": key, "read": 0, "ingested": 0, "error": ""}
            stats_by_key[key] = stat
            any_ok = True
            continue
        pending.append(portal)

    if pending:
        try:
            limit = int(workers if workers is not None else os.environ.get("PORTAL_WORKERS", "4"))
        except (TypeError, ValueError):
            limit = 4
        limit = max(1, min(8, limit, len(pending)))
        worker_count = limit
        remaining = {row.get("key") or "" for row in pending}
        checkpoint["current"] = ",".join(sorted(remaining))
        write_json_atomic(checkpoint_path(data_dir), checkpoint)

        def fetch_one(portal):
            def is_new(record: RawRecord) -> bool:
                if not record.job_id:
                    return True
                previous = redis.hget(BODY_KEY, f"{record.source}\0{record.job_id}")
                return previous != format_simhash(simhash64(record.body))

            return fetch_portal(portal, http=http, sleep=sleep, is_new=is_new)

        with ThreadPoolExecutor(max_workers=limit, thread_name_prefix="portal") as pool:
            futures = {pool.submit(fetch_one, portal): portal for portal in pending}
            for future in as_completed(futures):
                portal = futures[future]
                key = portal.get("key") or ""
                stat = None
                try:
                    records = future.result()
                    written = ingest_records(records, out_dir=out_dir, redis=redis, on_evidence=on_evidence)
                    any_ok = True
                    stat = {"key": key, "read": len(records), **written, "error": ""}
                    checkpoint["portals"][key] = {"status": "done", "stats": stat}
                except Exception as exc:
                    error = str(exc)[:300]
                    emit_collect_event(redis, EVENT_COLLECT_PORTAL_FAILED, {"key": key, "error": error})
                    stat = {"key": key, "read": 0, "ingested": 0, "skipped_fingerprint": 0, "skipped_near_dup": 0, "error": error}
                    checkpoint["portals"][key] = {"status": "failed", "stats": stat}
                except BaseException:
                    _flush_evidence(on_evidence)
                    write_json_atomic(checkpoint_path(data_dir), checkpoint)
                    raise
                finally:
                    if stat is not None:
                        stats_by_key[key] = stat
                        remaining.discard(key)
                        checkpoint["current"] = ",".join(sorted(remaining))
                        _flush_evidence(on_evidence)
                        write_json_atomic(checkpoint_path(data_dir), checkpoint)
    checkpoint["status"] = "completed"
    checkpoint["current"] = ""
    checkpoint["finished_at"] = datetime.now().astimezone().isoformat()
    write_json_atomic(checkpoint_path(data_dir), checkpoint)
    portal_stats = [stats_by_key[row.get("key") or ""] for row in portals if row.get("key") in stats_by_key]
    emit_collect_event(redis, EVENT_COLLECT_FINISHED, {"portals": portal_stats})
    return {"ok": any_ok, "resumed": resumed, "workers": worker_count, "portals": portal_stats}
