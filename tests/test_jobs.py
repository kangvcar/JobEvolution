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
    assert JOB_TARGET_NAMES == (
        "大模型应用工程师",
        "机器学习工程师",
        "算法工程师",
        "多模态算法工程师",
        "Agent 工程师",
        "模型评测工程师",
        "提示词工程师",
        "数据工程师",
        "数据分析师",
        "数据科学家",
        "实时计算工程师",
        "嵌入式智能工程师",
        "自动驾驶感知工程师",
        "机器人软件工程师",
        "物联网应用开发工程师",
        "物联网平台工程师",
        "边缘计算工程师",
    )
