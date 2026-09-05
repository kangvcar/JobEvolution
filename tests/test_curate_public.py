from app.pipeline.curate_public import _definition_claim, canonical_name, rank_requirements
from app import graph
import json


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


def test_rank_requirements_keeps_a_requirement_group_on_one_kind():
    group = [
        {"skill_id": "python", "name": "Python", "kind": "required", "group_id": "g1", "min_required": 1, "confidence": 1, "sources": ["a", "b", "c", "d"]},
        {"skill_id": "ts", "name": "TypeScript", "kind": "required", "group_id": "g1", "min_required": 1, "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "go", "name": "Go", "kind": "required", "group_id": "g1", "min_required": 1, "confidence": 1, "sources": ["a", "b"]},
    ]
    standalone = [
        {"skill_id": f"s{i}", "name": f"技能{i}", "kind": "required", "confidence": 1, "sources": ["a", "b", "c"]}
        for i in range(12)
    ]

    result = rank_requirements(group + standalone, {"a", "b", "c", "d"}, max_required=12, max_formal=24)

    members = {row["skill_id"]: row for row in result["selected"] if row.get("group_id") == "g1"}
    assert set(members) == {"python", "ts", "go"}
    assert {row["kind"] for row in members.values()} == {"required"}
    assert result["counts"]["required"] == 12
    assert sum(row["kind"] == "bonus" for row in result["selected"]) == 1


def test_rank_requirements_shrinks_min_required_and_ungroups_single_survivor():
    rows = [
        {"skill_id": "python", "name": "Python", "kind": "required", "group_id": "g1", "min_required": 2, "confidence": 1, "sources": ["a"]},
        {"skill_id": "gpt", "name": "GPT", "kind": "required", "group_id": "g1", "min_required": 2, "confidence": 1, "sources": ["a"]},
    ]

    result = rank_requirements(rows, {"a"})

    assert [(row["skill_id"], row.get("group_id"), row.get("min_required")) for row in result["selected"]] == [("python", None, None)]


def test_definition_claim_only_keeps_fragments_verbatim_in_evidence():
    bodies = {
        "e1": "2、熟悉C/C++软件开发与调试，熟悉MATLAB",
        "e2": "3、拆解和参与预测模块（行为预测、轨迹预测等）、决策规划模块的设计与开发；熟悉C/C++软件开发与调试",
    }
    events = [
        {"review": "approved", "payload": {"excerpt": "参与预测模块（行为预测、轨迹预测等）的设计与开发", "sources": ["e1", "e2"]}},
        {"review": "approved", "payload": {"excerpt": "熟悉C/C++软件开发与调试", "sources": ["e1", "e2"]}},
        {"review": "approved", "payload": {"excerpt": "熟悉MATLAB", "sources": ["e1", "e2"]}},
    ]

    claims = _definition_claim("感知岗", events, bodies)

    assert claims[0]["text"] == "感知岗的招聘信息主要围绕：熟悉C/C++软件开发与调试；熟悉MATLAB"
    assert claims[0]["sources"] == ["e1", "e2"]
    assert _definition_claim("感知岗", events[:1], bodies) == []


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


def test_public_curation_keeps_a_definition_that_already_matches_evidence(tmp_path):
    job_id = "job-curation-keep-definition"
    graph.init_graph()
    graph.upsert_job(id=job_id, name="定义保留岗", domain="ai", status="formed")
    evidence = []
    for i, body in enumerate(["熟练掌握 Python 与 SQL；负责检索服务开发", "熟练掌握 Python 与 SQL；参与数据建模"]):
        eid = f"{job_id}-e{i}"
        path = tmp_path / f"{eid}.json"
        path.write_text(json.dumps({"body": body}, ensure_ascii=False), encoding="utf-8")
        graph.upsert_evidence_many([{"id": eid, "path": str(path), "source": "test", "company": f"公司{i}", "observed_at": "2026-01-01"}])
        graph.link_evidence(eid, job_id)
        evidence.append(eid)
    graph.apply_requires({"job_id": job_id, "job_name": "定义保留岗", "domain": "ai", "skill_id": f"{job_id}-py", "skill_name": "Python", "kind_edge": "required", "sources": evidence, "excerpt": "熟练掌握 Python"})
    graph.upsert_event({"id": f"{job_id}-evt", "kind": "requires_add", "review": "approved", "payload": {"job_id": job_id, "excerpt": "熟练掌握 Python 与 SQL", "sources": evidence}}, job_id, create_proposal=False)
    verified = "定义保留岗的招聘信息主要围绕：熟练掌握 Python 与 SQL；负责检索服务开发"
    graph.apply_definition_claims(job_id, [{"type": "responsibility", "text": verified, "sources": evidence}], event_id="seed")
    try:
        from app.pipeline.curate_public import curate_public_jobs

        curate_public_jobs(publish_release=False)
        claims = graph.current_definition(job_id)
        assert [row["text"] for row in claims] == [verified]
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (j:Job {id: $id}) OPTIONAL MATCH (j)-[:HAS_DEFINITION]->(d) OPTIONAL MATCH (d)-[:HAS_CLAIM]->(c) OPTIONAL MATCH (j)-[:REQUIRES_VERSION]->(v) DETACH DELETE j, d, c, v", id=job_id)
            session.run("MATCH (e:Evidence) WHERE e.id STARTS WITH $p DETACH DELETE e", p=job_id)
            session.run("MATCH (e:EvolutionEvent) WHERE e.id STARTS WITH $p DETACH DELETE e", p=job_id)
