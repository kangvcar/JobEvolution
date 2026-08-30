from app.targets import JOB_TARGET_NAMES


def test_jobs_empty_without_seeded_nodes(client):
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []
    names = {row["name"] for row in response.json()}
    assert names.isdisjoint(JOB_TARGET_NAMES)


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


def test_seventeen_align_targets_exist():
    assert len(JOB_TARGET_NAMES) == 17
    assert "大模型应用工程师" in JOB_TARGET_NAMES
    assert "Agent 工程师" in JOB_TARGET_NAMES
    assert "边缘计算工程师" in JOB_TARGET_NAMES
