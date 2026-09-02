from app.pipeline.diagnostic_release import validate_diagnostic_release
from app import graph


def _requires(n: int, *, start: int = 0):
    return [
        {
            "skill_id": f"s{i + start}",
            "kind": "required",
            "sources": [f"e{i + start}"],
            "excerpt": f"需要 s{i + start}",
        }
        for i in range(n)
    ]


def test_empty_definition_and_missing_evidence_block_release():
    result = validate_diagnostic_release(
        job_id="job-1",
        definition=[],
        requires=[{"skill_id": "s1", "kind": "required", "sources": [], "excerpt": ""}],
        evidence=[],
    )
    assert not result["ok"]
    assert {item["code"] for item in result["errors"]} >= {"definition_missing", "evidence_missing"}


def test_twenty_five_required_is_anomaly_and_override_only_clears_anomaly():
    requires = _requires(25)
    evidence = [{"id": f"e{i}", "retracted": False} for i in range(25)]
    blocked = validate_diagnostic_release(
        job_id="job-1",
        definition=[{"text": "负责服务开发"}],
        requires=requires,
        evidence=evidence,
    )
    assert not blocked["ok"]
    assert any(item["code"] == "required_count_exceeded" for item in blocked["errors"])
    released = validate_diagnostic_release(
        job_id="job-1",
        definition=[{"text": "负责服务开发"}],
        requires=requires,
        evidence=evidence,
        override_reason="数据迁移后人工核对，保留本版本",
    )
    assert not released["ok"]
    assert any(item["code"] == "required_count_exceeded" for item in released["errors"])


def test_delta_anomaly_can_be_released_with_reason():
    current = _requires(10)
    previous = _requires(3)
    evidence = [{"id": f"e{i}", "retracted": False} for i in range(10)]
    blocked = validate_diagnostic_release(
        job_id="job-1", definition=[{"text": "负责服务开发"}], requires=current, evidence=evidence, previous_requires=previous
    )
    assert any(item["code"] == "required_delta_anomaly" for item in blocked["errors"])
    released = validate_diagnostic_release(
        job_id="job-1", definition=[{"text": "负责服务开发"}], requires=current, evidence=evidence, previous_requires=previous, override_reason="人工复核新增职责"
    )
    assert released["ok"]
    assert released["override"]["reason"]


def test_admin_release_endpoint_returns_structured_codes(client):
    job_id = "job-release-check"
    graph.init_graph()
    graph.upsert_job(id=job_id, name="校验岗", domain="ai", status="emerging")
    try:
        response = client.get("/admin/jobs/job-release-check/diagnostic-release", headers={"X-Admin-Password": "change-me"})
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert response.json()["errors"][0]["code"] == "definition_missing"
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id)


def test_bulk_approval_is_idempotent_and_does_not_call_review_model(client, monkeypatch):
    from app import main

    event = {
        "id": "evt-bulk-1",
        "review": "pending",
        "payload": {
            "kind": "requires_add",
            "job_id": "job-bulk",
            "version_id": "v1",
            "skill_id": "s1",
            "skill_name": "FastAPI",
            "proposed_kind": "required",
            "sources": ["e1", "e2"],
            "excerpt": "熟悉 FastAPI",
        },
    }
    audit = {"id": "bulk-any", "event_ids": ["evt-bulk-1"]}
    calls = []
    monkeypatch.setattr(graph, "get_any_job", lambda _: {"id": "job-bulk", "name": "岗"})
    monkeypatch.setattr(graph, "list_pending_events", lambda: [event])
    monkeypatch.setattr(graph, "list_requires", lambda _: [])
    monkeypatch.setattr(graph, "current_definition", lambda _: [{"text": "负责服务开发"}])
    monkeypatch.setattr(graph, "list_job_evidence", lambda *_args, **_kwargs: [{"id": "e1"}, {"id": "e2"}])
    monkeypatch.setattr(graph, "list_requires_history", lambda _: [])
    monkeypatch.setattr(main, "apply_event", lambda event_id, **kwargs: calls.append(event_id))
    monkeypatch.setattr(graph, "get_bulk_decision", lambda _: None if len(calls) == 0 else audit)
    monkeypatch.setattr(graph, "record_bulk_decision", lambda **kwargs: audit.update(kwargs))

    first = client.post("/admin/jobs/job-bulk/versions/v1/approve-all", headers={"X-Admin-Password": "change-me"}, json={})
    assert first.status_code == 200
    assert calls == ["evt-bulk-1"]
    second = client.post("/admin/jobs/job-bulk/versions/v1/approve-all", headers={"X-Admin-Password": "change-me"}, json={})
    assert second.status_code == 200
    assert second.json()["idempotent"] is True
    assert calls == ["evt-bulk-1"]
