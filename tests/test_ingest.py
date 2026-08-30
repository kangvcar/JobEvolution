import json
from pathlib import Path

from app.collectors import (
    MemoryRedis,
    classify_domain,
    independent_companies,
    list_snapshot_paths,
    normalize_company,
    run_ingest,
)
from app.collectors.sink import EVENT_JD_INGESTED
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
