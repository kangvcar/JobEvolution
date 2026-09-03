import uuid

from app import graph

ADMIN = "change-me"


def test_review_stats_counts_today_and_pass_rate(client):
    graph.init_graph()
    tag = f"stats-{uuid.uuid4().hex[:8]}"
    before = client.get("/admin/review/stats", headers={"X-Admin-Password": ADMIN}).json()
    graph.record_review_decision(f"{tag}-a", review="approved", payload={"tag": tag})
    graph.record_review_decision(f"{tag}-b", review="rejected", payload={"tag": tag})
    graph.record_review_decision(f"{tag}-c", review="auto_passed", payload={"tag": tag})
    try:
        after = client.get("/admin/review/stats", headers={"X-Admin-Password": ADMIN}).json()
        assert after["today"]["approved"] - before["today"].get("approved", 0) == 1
        assert after["today"]["rejected"] - before["today"].get("rejected", 0) == 1
        assert after["today"]["auto_passed"] - before["today"].get("auto_passed", 0) == 1
        approved, rejected = after["total"]["approved"], after["total"]["rejected"]
        assert after["pass_rate"] == approved / (approved + rejected)
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (d:ReviewDecision) WHERE d.event_id STARTS WITH $tag DETACH DELETE d", tag=tag)


def test_skill_names_lookup(client):
    graph.init_graph()
    sid = f"skill-{uuid.uuid4().hex[:8]}"
    graph.upsert_skill({"id": sid, "name": "向量检索", "category": "engineering"})
    try:
        response = client.get(f"/admin/skills/names?ids={sid},missing-id", headers={"X-Admin-Password": ADMIN})
        assert response.status_code == 200
        assert response.json() == {sid: "向量检索"}
        assert client.get("/admin/skills/names?ids=x").status_code == 401
    finally:
        with graph._driver.session() as session:
            session.run("MATCH (s:Skill {id: $id}) DETACH DELETE s", id=sid)
