import uuid

from app.pipeline.status import job_id_for
from conftest import graph_clean


def _seed_job(graph, *, suffix: str, name: str, status: str, domain: str = "ai"):
    job_id = f"job-{status[:2]}-{suffix}-{name[:4]}"
    graph.upsert_job(id=job_id, name=f"{name}-{suffix}", domain=domain, status=status)
    return job_id


def test_discover_lists_every_formed_job_with_change_summary(client):
    from app import graph

    graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        seeded = {_seed_job(graph, suffix=suffix, name=f"成型全量{i}", status="formed") for i in range(4)}
        board = client.get("/discover").json()
        ids = {row["id"] for row in board["formed"]}
        assert seeded <= ids
        assert board["formed_total"] == len(board["formed"])
        card = next(row for row in board["formed"] if row["id"] in seeded)
        assert card["n_added"] == 0 and card["n_expired"] == 0
        assert card["last_change"] == ""
    finally:
        graph_clean(suffix)


def test_alias_not_in_discover_or_feed_candidate_count(client):
    from app import graph

    graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        target = _seed_job(graph, suffix=suffix, name="并入目标", status="formed")
        alias = _seed_job(graph, suffix=suffix, name="已判别名", status="candidate")
        graph.set_alias(alias, target)
        client
        board = client.get("/discover").json()
        names = {row["name"] for row in board["candidate"]}
        assert f"已判别名-{suffix}" not in names
        feed = client.get("/feed").json()
        assert feed["candidate"] == len(board["candidate"])
        dossier = client.get(f"/discover/{target}").json()
        assert any(row["id"] == alias for row in dossier.get("aliases_in") or [])
    finally:
        graph_clean(suffix)


def test_candidate_dossier_visible_jobs_hidden(client):
    from app import graph

    graph.init_graph()
    suffix = uuid.uuid4().hex[:8]
    try:
        job_id = _seed_job(graph, suffix=suffix, name="卷宗候选", status="candidate")
        eid = f"jd-disc-{suffix}"
        graph.upsert_evidence_many(
            [
                {
                    "id": eid,
                    "path": f"/tmp/{eid}.json",
                    "source": "local",
                    "company": "甲",
                    "observed_at": "2024-06-01",
                    "simhash": "0" * 16,
                }
            ]
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
        client
        assert client.get(f"/jobs/{job_id}").status_code == 404
        dossier = client.get(f"/discover/{job_id}").json()
        assert dossier["status"] == "candidate"
        assert dossier["evidence"]
        assert dossier["events"]
        assert dossier["n_sources"] >= 1
        assert dossier["cluster"]["n"] == len(dossier["evidence"])
        assert "watching" not in dossier
        assert dossier["requires"] == []
        assert set(dossier["events"][0]) == {"id", "kind", "at", "review", "skill_name", "excerpt"}
    finally:
        graph_clean(suffix)


def test_feed_counts_and_stories_from_graph(client):
    from app import graph

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
        client
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
        graph_clean(suffix)
        with graph._driver.session() as session:
            session.run("MATCH (s:Skill {id: $id}) DETACH DELETE s", id=f"skill-{suffix}")


def test_contest_pair_stories_when_present(client):
    client
    jobs = {row["name"]: row for row in client.get("/jobs").json()}
    feed = client.get("/feed").json()
    by_kind = {row["kind"]: row for row in feed["stories"]}
    if "Agent 工程师" in jobs and jobs["Agent 工程师"]["status"] == "emerging":
        assert by_kind["discover"]["name"] == "Agent 工程师"
        assert by_kind["discover"]["job_id"] == job_id_for("Agent 工程师")
    if "大模型应用工程师" in jobs and jobs["大模型应用工程师"]["status"] == "formed":
        assert by_kind["update"]["name"] == "大模型应用工程师"
        assert by_kind["update"]["job_id"] == job_id_for("大模型应用工程师")
