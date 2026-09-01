import os
import uuid

from app.pipeline.constants import EMERGING_SOURCES, EMERGING_WINDOW_DAYS, FORMED_SOURCES
from app.pipeline.gate import apply_event, run_extract_and_gate
from app.pipeline.status import compute_status, job_id_for, source_stats
from conftest import graph_clean

ADMIN = os.environ.get("ADMIN_PASSWORD", "change-me")


def test_skill_relink_keeps_one_category_edge():
    from app import graph

    graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    sid = f"skill-cat-{suffix}"
    job_id = f"job-cat-{suffix}"
    try:
        graph.upsert_skill({"id": sid, "name": f"重类目{suffix}", "synonyms": [], "category": "framework"})
        graph.upsert_skill({"id": sid, "name": f"重类目{suffix}", "synonyms": [], "category": "platform"})
        with graph._driver.session() as session:
            cats = session.run(
                "MATCH (s:Skill {id: $id})-[:IN_CATEGORY]->(c) RETURN collect(c.id) AS cats",
                id=sid,
            ).single()["cats"]
        assert cats == ["platform"]
        graph.upsert_job(id=job_id, name=f"类目扇出{suffix}", domain="ai", status="emerging")
        with graph._driver.session() as session:
            session.run(
                "MATCH (j:Job {id: $id}), (s:Skill {id: $sid}) MERGE (j)-[:REQUIRES]->(s)",
                id=job_id,
                sid=sid,
            )
        assert graph.list_requires(job_id) != []
        assert len(graph.list_requires(job_id)) == 1
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (s:Skill {id: $sid}) DETACH DELETE s", sid=sid)
            session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id)


def test_compute_status_thresholds():
    assert (
        compute_status(
            n_window=2,
            n_total=2,
            span_days=10,
            definition_passed=False,
            judged_new=True,
        )
        == "candidate"
    )
    assert (
        compute_status(
            n_window=EMERGING_SOURCES,
            n_total=EMERGING_SOURCES,
            span_days=10,
            definition_passed=False,
            judged_new=True,
        )
        == "emerging"
    )
    assert (
        compute_status(
            n_window=EMERGING_SOURCES,
            n_total=FORMED_SOURCES,
            span_days=10,
            definition_passed=True,
            judged_new=True,
        )
        == "formed"
    )
    assert (
        compute_status(
            n_window=EMERGING_SOURCES,
            n_total=3,
            span_days=200,
            definition_passed=True,
            judged_new=True,
        )
        == "formed"
    )
    assert (
        compute_status(
            n_window=EMERGING_SOURCES,
            n_total=3,
            span_days=10,
            definition_passed=False,
            judged_new=False,
        )
        == "candidate"
    )


def test_source_stats_window_and_channels():
    n_window, n_total, span = source_stats(
        [
            {"company": "甲有限公司", "observed_at": "2024-06-01"},
            {"company": "乙", "observed_at": "2024-06-10"},
            {"company": "丙", "observed_at": "2024-06-20"},
            {"company": "Greenhouse", "observed_at": "2024-06-20"},
            {"company": "丁", "observed_at": "2023-01-01"},
        ]
    )
    assert n_total == 4
    assert n_window == 3
    assert span >= EMERGING_WINDOW_DAYS


def test_candidate_hidden_without_password(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    job_id = f"job-cand-{suffix}"
    graph.init_graph()
    graph.upsert_job(id=job_id, name=f"候选测试{suffix}", domain="ai", status="candidate")
    assert client.get(f"/jobs/{job_id}").status_code == 404
    assert client.get(f"/graph/jobs/{job_id}").status_code == 404
    assert client.post("/diagnose", json={"job_id": job_id}).status_code == 400
    names = {row["name"] for row in client.get("/jobs").json()}
    assert f"候选测试{suffix}" not in names
    with graph._driver.session() as session:
        session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id)


def test_agent_engineer_emerging_with_three_sources(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snaps = _snaps(
        tmp_path,
        suffix,
        "Agent 工程师",
        companies=("甲", "乙", "丙"),
        at="2024-06-01",
    )
    events = run_extract_and_gate(
        snaps, complete_json=_extract("Agent 工程师", "FastAPI"), workers=1
    )
    _no_extract_failed(events)
    for event in events:
        if event.get("review") == "pending":
            client.post(
                f"/admin/queue/{event['id']}/approve",
                headers={"X-Admin-Password": ADMIN},
                json={},
            )
    job_id = job_id_for("Agent 工程师")
    row = client.get(f"/jobs/{job_id}").json()
    assert row["name"] == "Agent 工程师"
    assert row["status"] == "emerging"
    graph_clean(suffix)


def test_llm_app_requires_and_period_delta(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    name = "大模型应用工程师"
    old = _snaps(tmp_path, suffix + "a", name, companies=("甲", "乙", "丙"), at="2023-03-01")
    events = run_extract_and_gate(old, complete_json=_extract(name, "FastAPI"), workers=1)
    _no_extract_failed(events)
    for event in events:
        if event.get("review") == "pending":
            apply_event(event["id"], review="approved")
    new = _snaps(tmp_path, suffix + "b", name, companies=("丁", "戊", "己"), at="2024-06-01")
    events2 = run_extract_and_gate(new, complete_json=_extract(name, "Neo4j"), workers=1)
    _no_extract_failed(events2)
    for event in events2:
        if event.get("review") == "pending":
            apply_event(event["id"], review="approved")
    job_id = job_id_for(name)
    slice_ = client.get(f"/graph/jobs/{job_id}").json()
    assert slice_["requires"]
    delta = slice_["period_delta"]
    assert delta["added"] or delta["expired"]
    assert any(edge["name"] == "FastAPI" for edge in delta["expired"])
    with graph._driver.session() as session:
        expired = session.run(
            """
            MATCH (j:Job {id: $id})-[r:REQUIRES]->(s:Skill {name: 'FastAPI'})
            RETURN r.valid_to AS valid_to
            """,
            id=job_id,
        ).single()
    assert expired is not None and expired["valid_to"] is not None
    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "formed"
    kinds = {e.get("kind") for e in detail.get("events") or []}
    assert "requires_add" in kinds
    graph_clean(suffix)


def test_alias_not_in_candidate_column(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    target = "大模型应用工程师"
    seed = _snaps(tmp_path, suffix + "t", target, companies=("甲", "乙", "丙"), at="2024-06-01")
    events = run_extract_and_gate(seed, complete_json=_extract(target, "FastAPI"), workers=1)
    for event in events:
        if event.get("review") == "pending":
            apply_event(event["id"], review="approved")
    alias_snaps = _snaps(
        tmp_path,
        suffix + "s",
        "LLM 业务工程师",
        companies=("庚", "辛", "壬"),
        at="2024-06-10",
    )
    events = run_extract_and_gate(
        alias_snaps,
        complete_json=_extract("LLM 业务工程师", "FastAPI", classify="alias"),
        workers=1,
    )
    _no_extract_failed(events)
    board = client.get("/discover").json()
    names = {row["name"] for row in board["candidate"]}
    assert "LLM 业务工程师" not in names
    alias_id = job_id_for("LLM 业务工程师")
    assert graph.has_alias_out(alias_id)
    graph_clean(suffix)


def _no_extract_failed(events):
    # 守卫：桩坏了会静默变成 extract_failed 事件，测试在空库上全部 vacuous pass（本地脏库还会假装全绿）
    failed = [e for e in events if e.get("kind") == "extract_failed"]
    assert not failed, f"抽取桩失败，事件里出现 extract_failed: {failed[:2]}"


def _extract(job_name, skill, classify=None):
    def complete(_messages):
        text = str(_messages)
        if "Classify" in text or "kind" in text and "alias_of" in text:
            if classify == "alias":
                return {"kind": "alias", "alias_of": "大模型应用工程师"}
            if classify == "new":
                return {"kind": "new", "alias_of": None}
            return {"kind": "noise", "alias_of": None}
        return {
            "job_name": job_name,
            "domain": "ai",
            "skills": [
                {
                    "name": skill,
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": f"熟悉 {skill}",
                    "section": "requirement",
                }
            ],
        }

    return complete


def _snaps(tmp_path, suffix, title, companies, at):
    from app import graph

    graph.init_graph()
    snaps = []
    body = f"任职要求：熟悉 FastAPI 与 {title}。"
    for i, company in enumerate(companies):
        sid = f"jd-st-{suffix}-{i}"
        doc = {
            "id": sid,
            "path": str(tmp_path / f"{sid}.json"),
            "source": "local",
            "company": company,
            "title": title,
            "body": body,
            "city": "北京",
            "observed_at": at if isinstance(at, str) else at,
            "domain": "ai",
            "fingerprint": sid,
            "simhash": "0" * 16,
        }
        graph.upsert_evidence_many(
            [
                {
                    "id": sid,
                    "path": doc["path"],
                    "source": "local",
                    "company": company,
                    "observed_at": doc["observed_at"],
                    "simhash": doc["simhash"],
                }
            ]
        )
        snaps.append(doc)
    return snaps
