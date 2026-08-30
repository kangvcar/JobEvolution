import os

from neo4j import GraphDatabase

DOMAINS = [
    {"id": "ai", "name": "人工智能"},
    {"id": "data", "name": "大数据"},
    {"id": "system", "name": "智能系统"},
    {"id": "iot", "name": "物联网"},
]

_CONSTRAINTS = (
    "CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (n:Domain) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT job_id IF NOT EXISTS FOR (n:Job) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT skill_category_id IF NOT EXISTS FOR (n:SkillCategory) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evolution_event_id IF NOT EXISTS FOR (n:EvolutionEvent) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX evolution_event_at IF NOT EXISTS FOR (n:EvolutionEvent) ON (n.at)",
)

_driver = None


def init_graph():
    global _driver
    _driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "jobevolution"),
        ),
    )
    with _driver.session() as session:
        for statement in _CONSTRAINTS:
            session.run(statement)
        for domain in DOMAINS:
            session.run(
                "MERGE (n:Domain {id: $id}) SET n.name = $name",
                id=domain["id"],
                name=domain["name"],
            )


def close_graph():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def list_domains():
    with _driver.session() as session:
        found = {
            row["id"]: row["name"]
            for row in session.run("MATCH (n:Domain) RETURN n.id AS id, n.name AS name")
        }
    return [{"id": d["id"], "name": found[d["id"]]} for d in DOMAINS if d["id"] in found]


def list_jobs(*, domain: str | None, status: str | None, q: str | None) -> list[dict]:
    if status == "candidate":
        return []
    cypher = """
    MATCH (j:Job)-[:IN_DOMAIN]->(d:Domain)
    WHERE j.status <> 'candidate'
      AND ($domain IS NULL OR d.id = $domain)
      AND ($status IS NULL OR j.status = $status)
      AND ($q IS NULL OR toLower(j.name) CONTAINS toLower($q))
    RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
           j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id
    """
    with _driver.session() as session:
        return [dict(row) for row in session.run(cypher, domain=domain, status=status, q=q)]


def get_public_job(job_id: str) -> dict | None:
    cypher = """
    MATCH (j:Job {id: $id})-[:IN_DOMAIN]->(d:Domain)
    WHERE j.status <> 'candidate'
    RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
           j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id
    """
    with _driver.session() as session:
        row = session.run(cypher, id=job_id).single()
    return dict(row) if row else None
