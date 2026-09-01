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


def test_unknown_job_is_404(client):
    response = client.get("/jobs/no-such-job")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body.get("detail") is None or isinstance(body["detail"], (str, type(None)))


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
