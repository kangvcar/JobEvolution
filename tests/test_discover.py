import uuid

from fastapi.testclient import TestClient

from app.pipeline.status import job_id_for


def _client():
    from app.main import app

    return TestClient(app)


def _seed_job(graph, *, suffix: str, name: str, status: str, domain: str = "ai"):
    job_id = f"job-{status[:2]}-{suffix}-{name[:4]}"
    graph.upsert_job(id=job_id, name=f"{name}-{suffix}", domain=domain, status=status)
    return job_id


def _cleanup(graph, suffix: str):
    if graph._driver is None:
        return
    with graph._driver.session() as session:
        session.run(
            "MATCH (j:Job) WHERE j.id CONTAINS $s OR j.name CONTAINS $s DETACH DELETE j",
            s=suffix,
        )
        session.run(
            "MATCH (e:Evidence) WHERE e.id CONTAINS $s DETACH DELETE e",
            s=suffix,
        )
        session.run(
            "MATCH (ev:EvolutionEvent) WHERE ev.id CONTAINS $s DETACH DELETE ev",
            s=suffix,
        )


def test_discover_formed_column_is_a_slice_of_three():
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        for i in range(4):
            _seed_job(graph, suffix=suffix, name=f"成型切片{i}", status="formed")
        client = _client()
        board = client.get("/discover").json()
        jobs = client.get("/jobs").json()
        formed_public = [row for row in jobs if row["status"] == "formed"]
        assert len(board["formed"]) <= 3
        assert len(formed_public) >= len(board["formed"])
        if len(formed_public) > 3:
            assert len(board["formed"]) == 3
    finally:
        _cleanup(graph, suffix)


def test_alias_not_in_discover_or_feed_candidate_count():
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        target = _seed_job(graph, suffix=suffix, name="并入目标", status="formed")
        alias = _seed_job(graph, suffix=suffix, name="已判别名", status="candidate")
        graph.set_alias(alias, target)
        client = _client()
        board = client.get("/discover").json()
        names = {row["name"] for row in board["candidate"]}
        assert f"已判别名-{suffix}" not in names
        feed = client.get("/feed").json()
        assert feed["candidate"] == len(board["candidate"])
        dossier = client.get(f"/discover/{target}").json()
        assert any(row["id"] == alias for row in dossier.get("aliases_in") or [])
    finally:
        _cleanup(graph, suffix)


def test_candidate_dossier_visible_jobs_hidden():
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        job_id = _seed_job(graph, suffix=suffix, name="卷宗候选", status="candidate")
        eid = f"jd-disc-{suffix}"
        graph.upsert_evidence(
            id=eid,
            path=f"/tmp/{eid}.json",
            source="local",
            company="甲",
            observed_at="2024-06-01",
            simhash="0" * 16,
        )
        graph.link_evidence(eid, job_id)
        graph.upsert_event(
            {
                "id": f"evt-{suffix}",
                "kind": "job_status",
                "at": "2024-06-01",
                "confidence": 0.5,
                "review": "pending",
                "payload": {"kind": "job_status", "job_id": job_id},
            },
            job_id,
        )
        client = _client()
        assert client.get(f"/jobs/{job_id}").status_code == 404
        dossier = client.get(f"/discover/{job_id}").json()
        assert dossier["status"] == "candidate"
        assert dossier["evidence"]
        assert dossier["events"]
        assert dossier["n_sources"] >= 1
        assert dossier["cluster"]["n"] == len(dossier["evidence"])
    finally:
        _cleanup(graph, suffix)


def test_feed_counts_and_stories_from_graph():
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        _seed_job(graph, suffix=suffix, name="萌芽故事", status="emerging")
        formed = _seed_job(graph, suffix=suffix, name="成型故事", status="formed")
        graph.apply_requires(
            {
                "job_id": formed,
                "job_name": f"成型故事-{suffix}",
                "domain": "ai",
                "skill_id": f"skill-{suffix}",
                "skill_name": "FastAPI",
                "kind_edge": "required",
                "proficiency": "able",
                "layer": "high",
                "confidence": 0.9,
                "sources": [],
                "excerpt": "熟悉 FastAPI",
                "valid_from": "2026-06-01",
            }
        )
        client = _client()
        jobs = client.get("/jobs").json()
        feed = client.get("/feed").json()
        assert feed["in_graph"] == len(jobs)
        assert feed["emerging"] == len([row for row in jobs if row["status"] == "emerging"])
        kinds = {row["kind"] for row in feed["stories"]}
        if any(row["status"] == "emerging" for row in jobs):
            assert "discover" in kinds
        if any(row["status"] == "formed" for row in jobs):
            assert "update" in kinds
        for story in feed["stories"]:
            assert story["job_id"]
            assert story["name"]
            assert story["kind"] in ("discover", "update")
            assert client.get(f"/jobs/{story['job_id']}").status_code == 200
        assert "pipeline" in feed
        assert "heat" in feed
        assert "events" in feed
    finally:
        _cleanup(graph, suffix)
        with graph._driver.session() as session:
            session.run("MATCH (s:Skill {id: $id}) DETACH DELETE s", id=f"skill-{suffix}")


def test_contest_pair_stories_when_present():
    client = _client()
    jobs = {row["name"]: row for row in client.get("/jobs").json()}
    feed = client.get("/feed").json()
    by_kind = {row["kind"]: row for row in feed["stories"]}
    if "Agent 工程师" in jobs and jobs["Agent 工程师"]["status"] == "emerging":
        assert by_kind["discover"]["name"] == "Agent 工程师"
        assert by_kind["discover"]["job_id"] == job_id_for("Agent 工程师")
    if "大模型应用工程师" in jobs and jobs["大模型应用工程师"]["status"] == "formed":
        assert by_kind["update"]["name"] == "大模型应用工程师"
        assert by_kind["update"]["job_id"] == job_id_for("大模型应用工程师")
