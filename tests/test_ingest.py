import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from app.collectors import (
    MemoryRedis,
    classify_domain,
    independent_companies,
    list_snapshot_paths,
    normalize_company,
    run_ingest,
)
from app.collectors.controller import (
    observed_sort_key,
    parse_observed_at,
    stable_observed_at,
    table_year,
)
from app.collectors.backfill_dates import DATE_COLUMN, backfill, backfill_tables
from app.collectors.simhash import format_simhash, simhash64
from app.collectors.sink import EVENT_JD_INGESTED, STREAM_KEY, emit_jd_ingested
from app.collectors.source import field_map, map_row

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"


def _ingest(tmp_path, redis=None):
    out_dir = tmp_path / "jd"
    redis = redis or MemoryRedis()
    stats = run_ingest(data_dir=FIXTURES, out_dir=out_dir, redis=redis)
    return stats, out_dir, redis


def test_column_mapping_across_two_table_shapes():
    zhilian = field_map(
        ["企业名称", "招聘岗位", "职位描述", "招聘发布日期", "工作城市", "来源", "岗位id"]
    )
    internet = field_map(["company", "name", "demand", "location"])
    assert zhilian is not None and internet is not None
    assert zhilian["company"] == "企业名称"
    assert internet["company"] == "company"
    assert zhilian["body"] == "职位描述"
    assert internet["body"] == "demand"

    mapped = map_row(
        {
            "企业名称": "甲有限公司",
            "招聘岗位": "算法工程师",
            "职位描述": "做算法",
            "招聘发布日期": "2024-01-01",
            "工作城市": "北京",
            "来源": "智联招聘",
            "岗位id": "42",
        },
        zhilian,
    )
    other = map_row(
        {
            "company": "乙",
            "name": "物联网应用开发工程师",
            "demand": "做物联网",
            "location": "深圳",
        },
        internet,
    )
    assert mapped.company == "甲有限公司"
    assert mapped.channel == "智联招聘"
    assert mapped.job_id == "42"
    assert other.company == "乙"
    assert other.title == "物联网应用开发工程师"
    assert other.body == "做物联网"

    it = field_map(
        ["岗位id", "岗位名", "岗位描述", "公司名称", "工作地区", "发布日期"]
    )
    zonghe = field_map(
        ["job_name", "company_name", "job_city", "publish_detail", "job_duty"]
    )
    software = field_map(["岗位", "公司", "城市", "岗位要求"])
    assert it is not None and zonghe is not None and software is not None
    assert it["title"] == "岗位名"
    assert it["company"] == "公司名称"
    assert it["body"] == "岗位描述"
    assert it["job_id"] == "岗位id"
    assert zonghe["title"] == "job_name"
    assert zonghe["company"] == "company_name"
    assert zonghe["body"] == "job_duty"
    assert software["title"] == "岗位"
    assert software["company"] == "公司"
    assert software["body"] == "岗位要求"
    both_titles = field_map(["岗位名", "岗位", "公司名称", "岗位描述"])
    assert both_titles is not None
    assert both_titles["title"] == "岗位名"


def test_missing_body_is_dropped(tmp_path):
    stats, out_dir, _ = _ingest(tmp_path)
    titles = {
        json.loads(path.read_text(encoding="utf-8"))["title"]
        for path in list_snapshot_paths(out_dir)
    }
    assert stats["dropped_body"] >= 1
    assert "算法岗位" not in titles


def test_domain_filter_and_ai_wins_on_overlap():
    assert classify_domain("机器学习工程师") == "ai"
    assert classify_domain("数据仓库工程师") == "data"
    assert classify_domain("嵌入式智能工程师") == "system"
    assert classify_domain("物联网应用开发工程师") == "iot"
    assert classify_domain("大数据算法工程师") == "ai"
    assert classify_domain("销售经理") is None


def test_company_normalization_strips_legal_suffix_and_paren_place():
    assert normalize_company("北京示例科技有限公司（海淀）") == "北京示例科技"
    assert normalize_company("杭州数界科技股份有限公司") == "杭州数界科技"


def test_same_fingerprint_skipped_on_second_run(tmp_path):
    redis = MemoryRedis()
    first, out_dir, redis = _ingest(tmp_path, redis)
    second = run_ingest(data_dir=FIXTURES, out_dir=out_dir, redis=redis)
    assert first["ingested"] >= 1
    assert second["ingested"] == 0
    assert second["skipped_fingerprint"] >= first["ingested"]
    assert second["paths"] == first["paths"]
    assert len(list_snapshot_paths(out_dir)) == first["paths"]


def test_simhash_near_dup_keeps_earliest_and_skips_independent_source(tmp_path):
    stats, out_dir, _ = _ingest(tmp_path)
    snapshots = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in list_snapshot_paths(out_dir)
    ]
    titles = {row["title"] for row in snapshots}
    assert "机器学习工程师" in titles
    assert "机器学习专家" not in titles
    kept = next(row for row in snapshots if row["title"] == "机器学习工程师")
    assert kept["observed_at"].startswith("2024-01-01")
    companies = independent_companies(snapshots)
    assert "抄袭科技" not in companies
    assert stats["skipped_near_dup"] >= 1


def test_each_kept_ingest_emits_jd_ingested(tmp_path):
    stats, _, redis = _ingest(tmp_path)
    events = redis.xrange("jobs:events")
    assert len(events) == stats["ingested"]
    assert all(fields["type"] == EVENT_JD_INGESTED for _, fields in events)
    assert {fields["id"] for _, fields in events} == {
        path.stem for path in list_snapshot_paths(tmp_path / "jd")
    }


def test_independent_source_counts_normalized_company_not_channel(tmp_path):
    _, out_dir, _ = _ingest(tmp_path)
    snapshots = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in list_snapshot_paths(out_dir)
    ]
    companies = independent_companies(snapshots)
    assert "北京示例科技" in companies
    assert "杭州数界科技" in companies
    assert "智联招聘" not in companies
    assert "Greenhouse" not in companies
    assert "ATS" not in companies
    channels = {row["channel"] for row in snapshots}
    assert "智联招聘" in channels or "Greenhouse" in channels
    assert all(row["source"] == "local" for row in snapshots)


def test_parse_observed_at_invalid_calendar_returns_empty():
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(50)
    try:
        assert parse_observed_at("2024-13-01") == ""
        assert parse_observed_at("2024-02-30") == ""
        assert parse_observed_at("2024.00.01") == ""
        assert parse_observed_at("发布于 2024-13-01 截止") == ""
        assert parse_observed_at("2024-01-02") == "2024-01-02T00:00:00"
        assert parse_observed_at("2025-05-12 14:20:34") == "2025-05-12T14:20:34"
        assert parse_observed_at("合肥 硕士 招10人 03-14发布", 2026) == "2026-03-14T00:00:00"
        assert parse_observed_at("广州 5-7年经验 本科 招若干人 03-14发布", 2026) == "2026-03-14T00:00:00"
        assert parse_observed_at("03-14发布") == ""
    finally:
        sys.setrecursionlimit(old)


def test_stable_observed_at_and_table_year():
    assert stable_observed_at("0" * 64, 2026) == "2026-01-01T00:00:00"
    assert stable_observed_at("f" * 64, 2026) == stable_observed_at("f" * 64, 2026)
    assert table_year("综合招聘数据库2026.csv") == 2026
    assert table_year("table.csv") is None


def test_backfill_dates_matches_source_and_counts_unmatched(tmp_path):
    data_dir = tmp_path / "data"
    out_dir = data_dir / "jd"
    out_dir.mkdir(parents=True)
    source = data_dir / "综合招聘数据库2026.csv"
    source.write_text(
        "企业名称,招聘岗位,职位描述,招聘发布日期,工作城市,岗位id\n"
        "甲,机器学习工程师,负责机器学习模型,合肥 硕士 招10人 03-14发布,合肥,42\n",
        encoding="utf-8",
    )
    from app.collectors.normalize import fingerprint_for

    fingerprint = fingerprint_for("local", "42", "甲", "机器学习工程师", "合肥")
    (out_dir / "jd-match.json").write_text(
        json.dumps({"fingerprint": fingerprint, "observed_at": ""}), encoding="utf-8"
    )
    (out_dir / "jd-miss.json").write_text(
        json.dumps({"fingerprint": "f" * 64, "observed_at": ""}), encoding="utf-8"
    )
    assert backfill(data_dir, out_dir) == {"filled": 1, "unmatched": 1, "skipped": 0}
    assert json.loads((out_dir / "jd-match.json").read_text())["observed_at"] == "2026-03-14T00:00:00"


def test_backfill_skips_source_without_year(tmp_path):
    data_dir = tmp_path / "data"
    out_dir = data_dir / "jd"
    out_dir.mkdir(parents=True)
    (data_dir / "table.csv").write_text(
        "企业名称,招聘岗位,职位描述\n甲,机器学习工程师,负责机器学习模型\n",
        encoding="utf-8",
    )
    assert backfill(data_dir, out_dir)["skipped"] == 1


def test_backfill_tables_adds_publish_date_and_keeps_blob(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    table = data_dir / "综合招聘数据库2026.csv"
    table.write_text(
        "job_name,company_name,job_city,publish_detail,job_duty\n"
        "机器学习工程师,甲,广州,广州 5-7年经验 本科 招若干人 03-14发布,负责机器学习模型\n",
        encoding="utf-8-sig",
        newline="\r\n",
    )
    assert backfill_tables(data_dir) == {"tables": 1, "skipped": 0}
    with table.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0][DATE_COLUMN] == "2026-03-14"
    assert "5-7年经验" in rows[0]["publish_detail"]
    assert "03-14发布" in rows[0]["publish_detail"]
    assert backfill_tables(data_dir) == {"tables": 0, "skipped": 1}


def test_backfill_tables_hashes_when_table_has_no_date_column(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    table = data_dir / "软件招聘数据库2026.csv"
    table.write_text(
        "岗位,公司,城市,岗位要求\n机器学习工程师,乙,杭州,负责机器学习模型\n",
        encoding="utf-8-sig",
        newline="\r\n",
    )
    assert backfill_tables(data_dir) == {"tables": 1, "skipped": 0}
    with table.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    date = rows[0][DATE_COLUMN]
    assert date.startswith("2026-")
    assert backfill_tables(data_dir)["skipped"] == 1



def test_missing_snapshot_with_fingerprint_is_rewritten(tmp_path):
    _, out_dir, redis = _ingest(tmp_path)
    victim = list_snapshot_paths(out_dir)[0]
    doc = json.loads(victim.read_text(encoding="utf-8"))
    victim.unlink()
    again = run_ingest(data_dir=FIXTURES, out_dir=out_dir, redis=redis)
    restored = out_dir / victim.name
    assert restored.exists()
    assert again["ingested"] >= 1
    event_ids = [fields["id"] for _, fields in redis.xrange(STREAM_KEY)]
    assert doc["id"] in event_ids


def test_existing_snapshot_without_fp_emits_jd_ingested(tmp_path):
    first, out_dir, redis = _ingest(tmp_path)
    redis._sets.clear()
    before = len(redis.xrange(STREAM_KEY))
    again = run_ingest(data_dir=FIXTURES, out_dir=out_dir, redis=redis)
    assert again["ingested"] == 0
    assert again["paths"] == first["paths"]
    assert len(redis.xrange(STREAM_KEY)) > before
    types = {fields["type"] for _, fields in redis.xrange(STREAM_KEY)}
    assert types == {EVENT_JD_INGESTED}


class _EvidenceStore:
    def __init__(self):
        self.nodes: dict[str, str] = {}

    def __call__(self, snapshot: dict) -> None:
        self.nodes[snapshot["id"]] = snapshot["company"]

    def drop(self, evidence_id: str) -> None:
        self.nodes.pop(evidence_id, None)


def test_earlier_near_dup_replaces_existing_snapshot(tmp_path):
    data_dir = tmp_path / "src"
    data_dir.mkdir()
    out_dir = tmp_path / "jd"
    redis = MemoryRedis()
    evidence = _EvidenceStore()
    body = "负责机器学习模型的训练评估与部署并与业务协作落地生产环境熟悉Python与PyTorch"
    (data_dir / "later.csv").write_text(
        "企业名称,招聘岗位,职位描述,招聘发布日期,工作城市,来源\n"
        f"后到科技,机器学习专家,{body},2024-08-01,杭州,\n",
        encoding="utf-8",
    )
    run_ingest(data_dir=data_dir, out_dir=out_dir, redis=redis, on_evidence=evidence)
    titles = {
        json.loads(path.read_text(encoding="utf-8"))["title"]
        for path in list_snapshot_paths(out_dir)
    }
    assert titles == {"机器学习专家"}
    assert set(evidence.nodes.values()) == {"后到科技"}
    (data_dir / "earlier.csv").write_text(
        "企业名称,招聘岗位,职位描述,招聘发布日期,工作城市,来源\n"
        f"先到科技有限公司,机器学习工程师,{body},2024-01-01,北京,\n",
        encoding="utf-8",
    )
    run_ingest(
        data_dir=data_dir, out_dir=out_dir, redis=redis, on_evidence=evidence
    )
    snapshots = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in list_snapshot_paths(out_dir)
    ]
    titles = {row["title"] for row in snapshots}
    assert "机器学习工程师" in titles
    assert "机器学习专家" not in titles
    kept = next(row for row in snapshots if row["title"] == "机器学习工程师")
    assert kept["observed_at"].startswith("2024-01-01")
    companies = independent_companies(snapshots)
    assert "先到科技" in companies
    assert "后到科技" not in companies
    assert set(evidence.nodes.values()) == {"先到科技"}
    assert kept["id"] in evidence.nodes
    assert len(evidence.nodes) == 1


def test_invalid_observed_at_on_disk_does_not_abort(tmp_path):
    assert observed_sort_key("not-a-date") == datetime.max
    assert observed_sort_key("") == datetime.max
    out_dir = tmp_path / "jd"
    out_dir.mkdir()
    body = "负责机器学习模型的训练评估与部署并与业务协作落地生产环境熟悉Python与PyTorch"
    (out_dir / "jd-badsnapshot0000.json").write_text(
        json.dumps(
            {
                "id": "jd-badsnapshot0000",
                "fingerprint": "cd" * 32,
                "simhash": format_simhash(simhash64(body)),
                "observed_at": "not-a-date",
                "domain": "ai",
                "company": "后到科技",
                "title": "机器学习专家",
                "body": body,
            }
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "src"
    data_dir.mkdir()
    (data_dir / "earlier.csv").write_text(
        "企业名称,招聘岗位,职位描述,招聘发布日期,工作城市,来源\n"
        f"先到科技有限公司,机器学习工程师,{body},2024-01-01,北京,\n",
        encoding="utf-8",
    )
    stats = run_ingest(data_dir=data_dir, out_dir=out_dir, redis=MemoryRedis())
    assert stats["ingested"] >= 1
    titles = {
        json.loads(path.read_text(encoding="utf-8"))["title"]
        for path in list_snapshot_paths(out_dir)
    }
    assert "机器学习工程师" in titles
    assert "机器学习专家" not in titles


def test_corrupt_simhash_does_not_abort_ingest(tmp_path):
    out_dir = tmp_path / "jd"
    out_dir.mkdir()
    (out_dir / "jd-deadbeefdeadbeef.json").write_text(
        json.dumps(
            {
                "id": "jd-deadbeefdeadbeef",
                "fingerprint": "ab" * 32,
                "simhash": "not-hex",
                "domain": "ai",
                "company": "噪声",
                "title": "坏快照",
            }
        ),
        encoding="utf-8",
    )
    stats = run_ingest(data_dir=FIXTURES, out_dir=out_dir, redis=MemoryRedis())
    assert stats["ingested"] >= 4
    titles = {
        json.loads(path.read_text(encoding="utf-8")).get("title")
        for path in list_snapshot_paths(out_dir)
    }
    assert "机器学习工程师" in titles


def test_jd_ingested_event_fields_not_stream_ids():
    redis = MemoryRedis()
    snapshot = {
        "id": "jd-abc",
        "path": "data/jd/jd-abc.json",
        "domain": "ai",
        "company": "示例",
        "title": "算法工程师",
        "fingerprint": "ff" * 32,
        "simhash": "0" * 16,
        "observed_at": "2024-01-01T00:00:00",
    }
    emit_jd_ingested(redis, snapshot)
    _entry_id, fields = redis.xrange(STREAM_KEY)[0]
    assert set(fields) == {"id", "type", "payload"}
    assert fields["id"] == "jd-abc"
    assert fields["type"] == EVENT_JD_INGESTED
    payload = json.loads(fields["payload"])
    assert payload["path"] == snapshot["path"]
    assert payload["fingerprint"] == snapshot["fingerprint"]


def test_fixture_ingest_lists_snapshot_paths_and_four_domains(tmp_path):
    stats, out_dir, _ = _ingest(tmp_path)
    paths = list_snapshot_paths(out_dir)
    assert stats["paths"] == len(paths) >= 4
    domains = {
        json.loads(path.read_text(encoding="utf-8"))["domain"] for path in paths
    }
    assert domains == {"ai", "data", "system", "iot"}
    assert stats["by_domain"]["ai"] >= 1
    assert stats["by_domain"]["data"] >= 1
    assert stats["by_domain"]["system"] >= 1
    assert stats["by_domain"]["iot"] >= 1
