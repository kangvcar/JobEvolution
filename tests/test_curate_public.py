from app.pipeline.curate_public import canonical_name, rank_requirements
from app import graph


def test_rank_requirements_filters_noise_deduplicates_and_caps():
    rows = [
        {"skill_id": "python", "name": "Python", "kind": "required", "confidence": 0.9, "sources": ["a", "b"]},
        {"skill_id": "prompt-en", "name": "Prompt Engineering", "kind": "required", "confidence": 0.9, "sources": ["a", "b", "c"]},
        {"skill_id": "prompt-zh", "name": "提示词工程", "kind": "required", "confidence": 0.8, "sources": ["a"]},
        {"skill_id": "gpt", "name": "GPT", "kind": "required", "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "team", "name": "团队协作", "kind": "required", "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "cv", "name": "CV", "kind": "required", "confidence": 0.7, "sources": ["a", "b"]},
        {"skill_id": "stale", "name": "Rust", "kind": "required", "confidence": 1, "sources": ["missing"]},
    ]
    result = rank_requirements(rows, {"a", "b", "c"}, max_required=1, max_formal=2)
    assert canonical_name("Prompt Engineering") == "提示词工程"
    assert result["counts"] == {"required": 1, "formal": 2}
    assert [row["name"] for row in result["selected"]] == ["提示词工程", "Python"]
    assert {row["skill_id"] for row in result["expired"]} >= {"gpt", "team", "stale"}


def test_rank_requirements_does_not_promote_bonus_to_required():
    rows = [
        {"skill_id": "bonus", "name": "FastAPI", "kind": "bonus", "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "required", "name": "Python", "kind": "required", "confidence": 0.5, "sources": ["a"]},
    ]

    result = rank_requirements(rows, {"a", "b"}, max_required=2, max_formal=2)

    assert [(row["skill_id"], row["kind"]) for row in result["selected"]] == [("required", "required"), ("bonus", "bonus")]


def test_public_curation_updates_the_versioned_requirements_and_caps_required():
    job_id = "job-curation-versioned"
    graph.init_graph()
    graph.upsert_job(id=job_id, name="版本化校准岗", domain="ai", status="emerging")
    evidence = [{"id": f"curation-e{i}", "company": f"公司{i}", "source": "test", "observed_at": "2026-01-01"} for i in range(14)]
    graph.upsert_evidence_many(evidence)
    for i, row in enumerate(evidence):
        graph.link_evidence(row["id"], job_id)
        graph.apply_requires({
            "job_id": job_id,
            "job_name": "版本化校准岗",
            "domain": "ai",
            "skill_id": f"curation-s{i}",
            "skill_name": f"技能{i}",
            "kind_edge": "required",
            "sources": [row["id"]],
            "excerpt": f"需要技能{i}",
        })
    try:
        from app.pipeline.curate_public import curate_public_jobs

        report = curate_public_jobs(publish_release=False)
        item = next(row for row in report["jobs"] if row["job_id"] == job_id)
        assert item["after"] == {"required": 12, "formal": 14}
        assert len(graph.list_requires(job_id)) == 14
        assert sum(row["kind"] == "required" for row in graph.list_requires(job_id)) == 12
        with graph._driver.session() as session:
            versioned = session.run(
                "MATCH (j:Job {id: $id})-[:REQUIRES_VERSION {active: true}]->() RETURN count(*) AS n",
                id=job_id,
            ).single()["n"]
        assert versioned == 14
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id)
            session.run("MATCH (e:Evidence) WHERE e.id STARTS WITH 'curation-e' DETACH DELETE e")
