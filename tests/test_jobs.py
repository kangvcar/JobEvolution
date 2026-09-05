from app.targets import JOB_TARGET_NAMES


def test_jobs_list_only_public_statuses(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    for row in response.json():
        assert row["status"] in ("emerging", "formed")


def test_candidate_filter_empty_without_password(client):
    response = client.get("/jobs", params={"status": "candidate"})
    assert response.status_code == 200
    assert response.json() == []


def test_diagnosable_jobs_filter_uses_the_release_gate(client, monkeypatch):
    from app import graph

    monkeypatch.setattr(
        graph,
        "list_jobs",
        lambda **_: [{"id": "ok", "name": "可诊断岗"}, {"id": "blocked", "name": "校验中岗位"}],
    )
    monkeypatch.setattr(graph, "diagnostic_release", lambda job_id: {"ok": job_id == "ok", "errors": []})

    response = client.get("/jobs", params={"diagnosable": "true"})

    assert response.status_code == 200
    assert response.json() == [{"id": "ok", "name": "可诊断岗"}]


def test_unknown_job_is_404(client):
    response = client.get("/jobs/no-such-job")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body.get("detail") is None or isinstance(body["detail"], (str, type(None)))


def test_job_detail_resolves_watching_skill_names(client, monkeypatch):
    from app import graph

    monkeypatch.setattr(graph, "get_public_job", lambda _: {"id": "job-1", "name": "岗位", "status": "formed", "watching": ["skill-1", "missing"]})
    monkeypatch.setattr(graph, "list_skills", lambda **_: [{"id": "skill-1", "name": "Python"}])
    monkeypatch.setattr(graph, "list_job_events", lambda _: [])
    monkeypatch.setattr(graph, "list_job_evidence", lambda _: [])
    monkeypatch.setattr(graph, "current_definition", lambda _: [])

    body = client.get("/jobs/job-1").json()
    assert body["watching"] == ["Python", "missing"]


def test_unknown_slice_is_404(client):
    response = client.get("/graph/jobs/no-such-job")
    assert response.status_code == 404


def test_public_slice_includes_categories_and_period_delta(client, monkeypatch):
    from app import graph

    monkeypatch.setattr(graph, "get_public_job", lambda _: {"id": "job-1", "name": "岗位", "status": "emerging"})
    monkeypatch.setattr(
        graph,
        "list_requires",
        lambda _: [{"skill_id": "skill-1", "name": "FastAPI", "category_id": "engineering", "category": "工程"}],
    )
    monkeypatch.setattr(graph, "period_delta", lambda _: {"added": [], "expired": []})

    body = client.get("/graph/jobs/job-1").json()
    assert body["categories"] == [{"id": "engineering", "name": "工程"}]
    assert body["skills"][0]["category"] == "工程"
    assert set(body["period_delta"]) == {"added", "expired"}


def test_seventeen_align_targets_exist():
    assert len(JOB_TARGET_NAMES) == 17
    assert "大模型应用工程师" in JOB_TARGET_NAMES
    assert "Agent 工程师" in JOB_TARGET_NAMES
    assert "边缘计算工程师" in JOB_TARGET_NAMES


def test_period_delta_chains_versions_and_ignores_curation_replacement(monkeypatch):
    from app import graph

    def _row(skill_id, name, valid_from, valid_to, curation_version=""):
        return {
            "skill_id": skill_id,
            "name": name,
            "category_id": None,
            "category": None,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "retracted": False,
            "curation_version": curation_version,
        }

    history = [
        # 同一技能三条历史版本：零时长版、被替代版、本季度失效版 → 一条链，只算一次 expired
        _row("skill-py", "Python", "2026-05-12T05:46:41Z", "2026-05-12T05:46:41Z"),
        _row("skill-py", "Python", "2026-05-12T05:46:41Z", "2026-08-04T03:44:24Z"),
        _row("skill-py", "Python", "2026-05-12T05:46:41Z", "2026-09-04T10:27:59Z"),
        # 本季度先失效、隔一段时间再出现 → 两条链，按最新链判定为 added，不同时出现在两边
        _row("skill-agent", "Agent", "2026-06-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        _row("skill-agent", "Agent", "2026-08-15T00:00:00Z", None),
        # 流水线两次改写签名、再被校准替换成带 curation_version 的活动版本：关闭时刻即下一行起点，
        # 是同一条要求的延续 → 本季度新增，绝不能算失效
        _row("skill-c", "C", "2026-09-01T06:54:48Z", "2026-09-04T06:59:10Z"),
        _row("skill-c", "C", "2026-09-04T06:59:10Z", "2026-09-04T10:27:59Z"),
        _row("skill-c", "C", "2026-09-04T10:27:59Z", None, curation_version="public-curation-v1"),
        # 上季度就在、被校准接续至今 → 稳定要求，两边都不出现
        _row("skill-sql", "SQL", "2026-04-01T00:00:00Z", "2026-09-04T10:27:59Z"),
        _row("skill-sql", "SQL", "2026-09-04T10:27:59Z", None, curation_version="public-curation-v1"),
        # 校准排名截断剔除（关闭行被打上 curation_version）→ 数据清洗，不算市场失效
        _row("skill-cut", "被截断", "2026-09-01T00:00:00Z", "2026-09-04T10:27:59Z", curation_version="public-curation-v1"),
        # 只有校准版本、没有流水线来源 → 不参与周期变化
        _row("skill-cur", "策展项", "2026-09-04T10:27:59Z", None, curation_version="public-curation-v1"),
        # 撤回的行不参与
        {**_row("skill-x", "撤回", "2026-09-01T00:00:00Z", None), "retracted": True},
    ]
    monkeypatch.setattr(graph, "list_requires_history", lambda _: history)

    delta = graph.period_delta("job-x")
    assert [r["skill_id"] for r in delta["expired"]] == ["skill-py"]
    assert sorted(r["skill_id"] for r in delta["added"]) == ["skill-agent", "skill-c"]
