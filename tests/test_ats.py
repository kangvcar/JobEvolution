import json
import threading
import time
from pathlib import Path

import pytest

from app.collectors.ats import (
    DEFAULT_PORTALS,
    SEARCH_WORDS,
    fetch_beisen,
    fetch_feishu,
    fetch_tencent,
    known_page_limit,
    keep_title,
    load_portals,
    run_official,
    strip_html,
    valid_host,
)
from app.collectors.controller import ingest_records, list_snapshot_paths
from app.collectors.source import RawRecord
from app.collectors.sink import (
    EVENT_COLLECT_FINISHED,
    EVENT_COLLECT_STARTED,
    STREAM_KEY,
)

from test_ingest import MemoryRedis

ADMIN = "change-me"


def test_default_sources_cover_system_iot_keywords():
    keys = {row["key"] for row in DEFAULT_PORTALS}
    assert {"agirobot", "tsingtengms", "asiainfo-sec", "lierda", "lg77oym6sy", "weikezhijia", "qianxun", "qijing", "tarsrobot", "thundersoft", "whales", "zhcomputing", "sudu", "x2-robot", "zhongqing-robot", "sharpa", "robot-era", "modelbest", "phigentai", "roboticplus", "hesai", "desaysv", "qcraft", "landspace", "shengshu", "blacklake", "ecoflow", "dcar", "zeron", "avatr", "shenfuture", "holitech", "vast", "lilithgames", "houmo", "carizon", "leadrive", "deeplang", "shenzhi", "bluefocus", "papergames", "brightchip"} <= keys
    assert sum(row["type"] == "feishu" and row["enabled"] for row in DEFAULT_PORTALS) == 50
    assert "arashivision" not in keys
    assert {"嵌入式", "机器人", "硬件", "物联网"} <= set(SEARCH_WORDS)


def test_keep_title_drops_intern_and_english():
    assert keep_title("大模型应用工程师", from_search=True)
    assert not keep_title("大模型实习生", from_search=True)
    assert not keep_title("Machine Learning Engineer", from_search=True)


def test_strip_html_plain_text():
    assert "Python" in strip_html("<p>熟悉 <b>Python</b></p>")
    assert "<" not in strip_html("<p>熟悉 <b>Python</b></p>")


def test_tencent_fetches_detail_after_title_filter():
    calls: list[str] = []

    def http(url, **kwargs):
        calls.append(url)
        if "Query" in url:
            return {
                "Data": {
                    "Posts": [
                        {
                            "PostId": "1",
                            "RecruitPostName": "大模型应用工程师",
                            "Responsibility": "列表摘要",
                            "LocationName": "深圳",
                            "PostURL": "https://careers.tencent.com/1",
                            "LastUpdateTime": "2026-01-02",
                        },
                        {
                            "PostId": "2",
                            "RecruitPostName": "大模型实习",
                            "Responsibility": "实习",
                            "LocationName": "深圳",
                        },
                    ]
                }
            }
        return {
            "Data": {
                "RecruitPostName": "大模型应用工程师",
                "Responsibility": "负责大模型应用落地",
                "Requirement": "Python",
                "LocationName": "深圳",
                "PostURL": "https://careers.tencent.com/1",
                "LastUpdateTime": "2026-01-02",
            }
        }

    rows = fetch_tencent(http=http, sleep=lambda: None)
    assert len(rows) == 1
    assert rows[0].job_id == "1"
    assert "Python" in rows[0].body
    assert any("ByPostId" in url for url in calls)
    assert not any("postId=2" in url for url in calls)


def test_beisen_fetches_public_job_json():
    calls = []

    def http(url, **kwargs):
        calls.append((url, kwargs))
        return {
            "Code": 200,
            "Count": 1,
            "Data": [
                {
                    "JobAdId": 511174092,
                    "JobAdName": "视觉大模型算法工程师",
                    "Duty": "负责机器人视觉算法",
                    "Require": "熟悉 Python、PyTorch",
                    "LocNames": ["杭州"],
                    "PostDate": "2026-08-01T00:00:00",
                }
            ],
        }

    rows = fetch_beisen("unitree.zhiye.com", "宇树科技", http=http, sleep=lambda: None)
    assert len(rows) == 1
    assert rows[0].job_id == "511174092"
    assert rows[0].domain == "ai"
    assert "PyTorch" in rows[0].body
    assert calls[0][0].endswith("/api/Jobad/GetJobAdPageList")


def test_feishu_stops_after_known_pages(monkeypatch):
    monkeypatch.setenv("COLLECT_KNOWN_PAGES", "2")
    first_word = SEARCH_WORDS[0]
    calls = []
    page = [
        {"id": f"known-{i}", "title": "算法工程师", "description": "负责算法", "requirement": "熟悉 Python"}
        for i in range(50)
    ]

    def http(url, **kwargs):
        body = kwargs.get("body") or {}
        if body.get("limit") == 1:
            return {"code": 0, "data": {"job_post_list": [{"id": "probe", "title": "算法工程师"}]}}
        calls.append((body.get("keyword"), body.get("offset")))
        if body.get("keyword") != first_word:
            return {"code": 0, "data": {"job_post_list": []}}
        offset = body.get("offset")
        if offset in (0, 50):
            return {"code": 0, "data": {"job_post_list": page}}
        return {"code": 0, "data": {"job_post_list": []}}

    rows = fetch_feishu("example.jobs.feishu.cn", "示例", http=http, sleep=lambda: None, is_new=lambda _: False)

    assert rows == []
    assert calls[:2] == [(first_word, 0), (first_word, 50)]
    assert (first_word, 100) not in calls


def test_known_page_limit_full_scan_override(monkeypatch):
    monkeypatch.setenv("COLLECT_KNOWN_PAGES", "2")
    assert known_page_limit() == 2
    monkeypatch.setenv("COLLECT_FULL_SCAN", "1")
    assert known_page_limit() == 0


def test_ats_new_body_writes_second_snapshot(tmp_path):
    redis = MemoryRedis()
    out_dir = tmp_path / "jd"
    first = RawRecord(
        company="腾讯",
        title="大模型应用工程师",
        body="第一版职责要求 Python",
        published_at="2026-01-01",
        city="深圳",
        channel="tencent",
        job_id="post-1",
        source="ats",
        domain="ai",
        observed_at="2026-01-01T00:00:00",
        url="https://example.com/1",
    )
    second = RawRecord(
        company="腾讯",
        title="大模型应用工程师",
        body="第二版职责要求 Python 与评测集",
        published_at="2026-06-01",
        city="深圳",
        channel="tencent",
        job_id="post-1",
        source="ats",
        domain="ai",
        observed_at="2026-06-01T00:00:00",
        url="https://example.com/1",
    )
    a = ingest_records([first], out_dir=out_dir, redis=redis)
    b = ingest_records([first], out_dir=out_dir, redis=redis)
    c = ingest_records([second], out_dir=out_dir, redis=redis)
    assert a["ingested"] == 1
    assert b["ingested"] == 0
    assert b["skipped_fingerprint"] == 1
    assert c["ingested"] == 1
    paths = list_snapshot_paths(out_dir)
    assert len(paths) == 2
    urls = {json.loads(path.read_text(encoding="utf-8"))["url"] for path in paths}
    assert "https://example.com/1" in urls


def test_ats_changed_near_duplicate_keeps_old_snapshot(tmp_path):
    redis = MemoryRedis()
    out_dir = tmp_path / "jd"
    first = RawRecord(
        company="腾讯",
        title="大模型应用工程师",
        body="负责大模型应用开发，熟悉 Python 与 FastAPI",
        published_at="2026-01-01",
        city="深圳",
        channel="tencent",
        job_id="post-near",
        source="ats",
        domain="ai",
        observed_at="2026-01-01T00:00:00",
    )
    second = RawRecord(**{**first.__dict__, "body": first.body + "，支持线上服务"})
    assert ingest_records([first], out_dir=out_dir, redis=redis)["ingested"] == 1
    assert ingest_records([second], out_dir=out_dir, redis=redis)["ingested"] == 1
    assert len(list_snapshot_paths(out_dir)) == 2


def test_host_validation_rejects_paths_and_accepts_feishu_host():
    assert valid_host("zhipu-ai.jobs.feishu.cn")
    assert not valid_host("zhipu-ai.jobs.feishu.cn/jobs")
    assert not valid_host("zhipu-ai.jobs.feishu.cn evil")
    assert not valid_host("https://zhipu-ai.jobs.feishu.cn")


def test_run_official_emits_collect_events(tmp_path):
    redis = MemoryRedis()
    (tmp_path / "portals.json").write_text(
        json.dumps(
            {
                "portals": [
                    {"key": "tencent", "type": "tencent", "name": "腾讯", "enabled": True, "builtin": True},
                    {"key": "dead", "type": "feishu", "name": "坏", "host": "nope.example", "enabled": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    def http(url, **kwargs):
        if "tencentcareer" in url and "Query" in url:
            return {
                "Data": {
                    "Posts": [
                        {
                            "PostId": "9",
                            "RecruitPostName": "机器学习工程师",
                            "Responsibility": "列表",
                            "LocationName": "北京",
                            "LastUpdateTime": "2026-02-02",
                        }
                    ]
                }
            }
        if "ByPostId" in url:
            return {
                "Data": {
                    "RecruitPostName": "机器学习工程师",
                    "Responsibility": "训练模型",
                    "Requirement": "PyTorch",
                    "LocationName": "北京",
                    "LastUpdateTime": "2026-02-02",
                    "PostURL": "https://careers.tencent.com/9",
                }
            }
        raise OSError("blocked")

    stats = run_official(
        data_dir=tmp_path,
        out_dir=tmp_path / "jd",
        redis=redis,
        http=http,
        sleep=lambda: None,
    )
    types = [fields["type"] for _, fields in redis._streams[STREAM_KEY]]
    assert EVENT_COLLECT_STARTED in types
    assert EVENT_COLLECT_FINISHED in types
    assert "collect_portal_failed" in types
    assert stats["ok"] is True
    assert any(row["key"] == "tencent" and row["ingested"] == 1 for row in stats["portals"])
    checkpoint = json.loads((tmp_path / "collect.checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "completed"


def test_official_checkpoint_resumes_finished_portal(tmp_path, monkeypatch):
    (tmp_path / "portals.json").write_text(
        json.dumps(
            {
                "portals": [
                    {"key": "first", "type": "fake", "name": "一", "enabled": True},
                    {"key": "second", "type": "fake", "name": "二", "enabled": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    calls = []
    interrupted = {"value": False}

    def fake_fetch(portal, **kwargs):
        calls.append(portal["key"])
        if portal["key"] == "second" and not interrupted["value"]:
            interrupted["value"] = True
            raise KeyboardInterrupt
        return []

    monkeypatch.setattr("app.collectors.ats.fetch_portal", fake_fetch)
    with pytest.raises(KeyboardInterrupt):
        run_official(data_dir=tmp_path, out_dir=tmp_path / "jd", redis=MemoryRedis(), sleep=lambda: None, workers=1)
    checkpoint = json.loads((tmp_path / "collect.checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "running"
    run = run_official(data_dir=tmp_path, out_dir=tmp_path / "jd", redis=MemoryRedis(), sleep=lambda: None, workers=1)
    assert run["resumed"] is True
    assert calls == ["first", "second", "second"]
    assert json.loads((tmp_path / "collect.checkpoint.json").read_text(encoding="utf-8"))["status"] == "completed"


def test_official_checkpoint_retries_failed_portal_after_completed_run(tmp_path, monkeypatch):
    portals = [{"key": key, "type": "fake", "name": key, "enabled": True} for key in ("done", "failed")]
    (tmp_path / "portals.json").write_text(json.dumps({"portals": portals}), encoding="utf-8")
    (tmp_path / "collect.checkpoint.json").write_text(
        json.dumps(
            {
                "version": 1,
                "status": "completed",
                "portals": {
                    "done": {"status": "done", "stats": {"key": "done", "read": 0, "ingested": 0}},
                    "failed": {"status": "failed", "stats": {"key": "failed", "read": 0, "ingested": 0}},
                },
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_fetch(portal, **kwargs):
        calls.append(portal["key"])
        return []

    monkeypatch.setattr("app.collectors.ats.fetch_portal", fake_fetch)
    result = run_official(data_dir=tmp_path, out_dir=tmp_path / "jd", redis=MemoryRedis(), workers=1)
    assert result["resumed"] is True
    assert calls == ["failed"]


def test_official_fetches_pending_portals_concurrently(tmp_path, monkeypatch):
    (tmp_path / "portals.json").write_text(
        json.dumps({"portals": [{"key": key, "type": "fake", "name": key, "enabled": True} for key in ("a", "b")]}),
        encoding="utf-8",
    )
    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_fetch(portal, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return []

    monkeypatch.setattr("app.collectors.ats.fetch_portal", fake_fetch)
    result = run_official(data_dir=tmp_path, out_dir=tmp_path / "jd", redis=MemoryRedis(), workers=2)
    assert result["workers"] == 2
    assert peak == 2


def test_load_portals_writes_defaults(tmp_path):
    rows = load_portals(tmp_path)
    assert Path(tmp_path / "portals.json").is_file()
    keys = {row["key"] for row in rows}
    assert {"tencent", "bytedance", "zhipu", "minimax", "moonshot"} <= keys


def test_events_stream_requires_admin(client):
    assert client.get("/events/stream").status_code == 401
    response = client.get("/admin/portals", headers={"X-Admin-Password": ADMIN})
    assert response.status_code == 200
    assert "portals" in response.json()
