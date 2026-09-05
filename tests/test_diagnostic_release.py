import json

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


def test_admin_can_rerun_public_curation(client, monkeypatch):
    from app.pipeline import curate_public

    monkeypatch.setattr(curate_public, "curate_public_jobs", lambda **kwargs: {"version": "test", "release": None, "jobs": []})

    response = client.post("/admin/public-curation", headers={"X-Admin-Password": "change-me"}, json={})

    assert response.status_code == 200
    assert response.json()["version"] == "test"


def test_approved_events_do_not_replace_a_missing_job_definition():
    job_id = "job-definition-required"
    event_id = "event-definition-required"
    graph.init_graph()
    graph.upsert_job(id=job_id, name="定义门槛岗", domain="ai", status="emerging")
    graph.upsert_event(
        {"id": event_id, "kind": "requires_add", "review": "approved", "payload": {"job_id": job_id}},
        job_id,
    )
    try:
        assert graph.definition_passed(job_id) is False
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id)
            session.run("MATCH (e:EvolutionEvent {id: $id}) DETACH DELETE e", id=event_id)


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


def test_mixed_kind_group_reports_members_and_reason():
    requires = [
        {"skill_id": "py", "name": "Python", "kind": "required", "group_id": "g1", "min_required": 1, "sources": ["e1"], "excerpt": "Python"},
        {"skill_id": "go", "name": "Go", "kind": "bonus", "group_id": "g1", "min_required": 1, "sources": ["e1"], "excerpt": "Go"},
    ]
    result = validate_diagnostic_release(
        job_id="job-1",
        definition=[{"text": "负责服务开发"}],
        requires=requires,
        evidence=[{"id": "e1", "retracted": False, "body": "精通 Python 或 Go"}],
    )
    error = next(item for item in result["errors"] if item["code"] == "invalid_requirement_group")
    assert error["group_id"] == "g1"
    assert error["reasons"] == ["mixed_kind"]
    assert {(member["skill_id"], member["kind"]) for member in error["members"]} == {("py", "required"), ("go", "bonus")}


def test_claim_fragment_details_pinpoint_the_paraphrased_fragment():
    definition = [{
        "id": "c1", "type": "responsibility", "sources": ["e1"],
        "text": "感知岗的招聘信息主要围绕：熟悉C/C++软件开发与调试；参与预测模块的设计与开发",
    }]
    result = validate_diagnostic_release(
        job_id="job-1",
        definition=definition,
        requires=[{"skill_id": "cpp", "name": "C++", "kind": "required", "sources": ["e1"], "excerpt": "C/C++"}],
        evidence=[{"id": "e1", "retracted": False, "body": "2、熟悉C/C++软件开发与调试，熟悉MATLAB；3、拆解和参与预测模块（行为预测）、决策规划模块的设计与开发"}],
    )
    error = next(item for item in result["errors"] if item["code"] == "evidence_missing")
    detail = next(item for item in error["details"] if item["target"] == "claim")
    assert detail["id"] == "c1"
    assert [(fragment["text"], fragment["supported"]) for fragment in detail["fragments"]] == [
        ("熟悉C/C++软件开发与调试", True),
        ("参与预测模块的设计与开发", False),
    ]


def _seed_repair_job(tmp_path, job_id: str, body: str):
    graph.init_graph()
    graph.upsert_job(id=job_id, name="修复岗", domain="ai", status="formed")
    evidence_id = f"{job_id}-e1"
    path = tmp_path / f"{evidence_id}.json"
    path.write_text(json.dumps({"body": body}, ensure_ascii=False), encoding="utf-8")
    graph.upsert_evidence_many([{"id": evidence_id, "path": str(path), "source": "test", "company": "公司A", "observed_at": "2026-01-01"}])
    graph.link_evidence(evidence_id, job_id)
    return evidence_id


def _cleanup_repair_job(job_id: str):
    with graph._driver.session() as session:
        session.run("MATCH (j:Job {id: $id}) OPTIONAL MATCH (j)-[:REQUIRES_VERSION]->(v) OPTIONAL MATCH (j)<-[:CORRECTS]-(c) OPTIONAL MATCH (j)-[:HAS_DEFINITION]->(d) OPTIONAL MATCH (d)-[:HAS_CLAIM]->(cl) DETACH DELETE j, v, c, d, cl", id=job_id)
        session.run("MATCH (e:Evidence) WHERE e.id STARTS WITH $prefix DETACH DELETE e", prefix=job_id)
        session.run("MATCH (g:RequirementGroup) WHERE g.id STARTS WITH $prefix DETACH DELETE g", prefix=job_id)


def test_admin_can_split_a_mixed_kind_requirement_group(client, tmp_path):
    job_id = "job-repair-group"
    evidence_id = _seed_repair_job(tmp_path, job_id, "精通 Python/TypeScript 等至少一种语言；了解 Go")
    group_id = f"{job_id}-g1"
    for skill, kind, excerpt in (("Python", "required", "精通 Python"), ("TypeScript", "bonus", "TypeScript"), ("Go", "bonus", "了解 Go")):
        graph.apply_requires({
            "job_id": job_id, "job_name": "修复岗", "domain": "ai", "skill_id": f"{job_id}-{skill}", "skill_name": skill,
            "kind_edge": kind, "sources": [evidence_id], "excerpt": excerpt, "group_id": group_id, "min_required": 1,
        })
    graph.apply_definition_claims(job_id, [{"type": "responsibility", "text": "修复岗的招聘信息主要围绕：精通 Python", "sources": [evidence_id]}], event_id="seed")
    try:
        before = client.get(f"/admin/jobs/{job_id}/diagnostic-release", headers={"X-Admin-Password": "change-me"}).json()
        assert [item["code"] for item in before["errors"]] == ["invalid_requirement_group"]
        response = client.post(
            f"/admin/jobs/{job_id}/requirement-groups/{group_id}",
            headers={"X-Admin-Password": "change-me"},
            json={"action": "split_by_kind", "reason": "校准把两条加分挤进了必备组"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["check"]["ok"] is True
        rows = {row["name"]: row for row in graph.list_requires(job_id)}
        # 单独剩下的必备退回独立要求；成员更多的加分那一侧保留原组 id。
        assert rows["Python"]["group_id"] is None
        assert rows["TypeScript"]["group_id"] == rows["Go"]["group_id"] == group_id
        assert rows["Go"]["min_required"] == 1 and rows["Go"]["kind"] == rows["TypeScript"]["kind"] == "bonus"
        with graph._driver.session() as session:
            audit = session.run("MATCH (c:GraphCorrection)-[:CORRECTS]->(:Job {id: $id}) RETURN c.action AS action, c.reason AS reason", id=job_id).single()
        assert audit["action"] == "group:split_by_kind" and audit["reason"]
    finally:
        _cleanup_repair_job(job_id)


def test_admin_can_drop_unsupported_claim_fragments(client, tmp_path):
    job_id = "job-repair-claim"
    evidence_id = _seed_repair_job(tmp_path, job_id, "2、熟悉C/C++软件开发与调试；3、拆解和参与预测模块、决策规划模块的设计与开发")
    graph.apply_requires({
        "job_id": job_id, "job_name": "修复岗", "domain": "ai", "skill_id": f"{job_id}-cpp", "skill_name": "C++",
        "kind_edge": "required", "sources": [evidence_id], "excerpt": "熟悉C/C++软件开发与调试",
    })
    graph.apply_definition_claims(job_id, [{
        "type": "responsibility", "sources": [evidence_id],
        "text": "修复岗的招聘信息主要围绕：熟悉C/C++软件开发与调试；参与预测模块的设计与开发",
    }], event_id="seed")
    claim_id = graph.current_definition(job_id)[0]["id"]
    try:
        before = client.get(f"/admin/jobs/{job_id}/diagnostic-release", headers={"X-Admin-Password": "change-me"}).json()
        assert [item["code"] for item in before["errors"]] == ["evidence_missing"]
        rejected = client.post(
            f"/admin/jobs/{job_id}/definition-claims/{claim_id}",
            headers={"X-Admin-Password": "change-me"},
            json={"action": "edit", "text": "修复岗的招聘信息主要围绕：负责一切"},
        )
        assert rejected.status_code == 409
        assert "负责一切" in rejected.json()["error"]
        response = client.post(
            f"/admin/jobs/{job_id}/definition-claims/{claim_id}",
            headers={"X-Admin-Password": "change-me"},
            json={"action": "drop_unsupported", "reason": "抽取改写了原文"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["check"]["ok"] is True
        claim = graph.current_definition(job_id)[0]
        assert claim["text"] == "修复岗的招聘信息主要围绕：熟悉C/C++软件开发与调试"
        assert claim["corrected_at"]
    finally:
        _cleanup_repair_job(job_id)
