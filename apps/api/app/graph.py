import json
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


_PUBLIC_JOB = """
MATCH (j:Job)-[:IN_DOMAIN]->(d:Domain)
WHERE (j.status IS NULL OR j.status <> 'candidate')
  AND ($domain IS NULL OR d.id = $domain)
  AND ($status IS NULL OR j.status = $status)
  AND ($q IS NULL OR toLower(j.name) CONTAINS toLower($q))
RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
       j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id
"""


def list_jobs(*, domain: str | None, status: str | None, q: str | None) -> list[dict]:
    if status == "candidate":
        return []
    with _driver.session() as session:
        return [dict(row) for row in session.run(_PUBLIC_JOB, domain=domain, status=status, q=q)]


def upsert_evidence(
    *,
    id: str,
    path: str,
    source: str,
    company: str,
    observed_at: str,
    simhash: str,
) -> None:
    upsert_evidence_many(
        [
            {
                "id": id,
                "path": path,
                "source": source,
                "company": company,
                "observed_at": observed_at,
                "simhash": simhash,
            }
        ]
    )


def upsert_evidence_many(rows: list[dict]) -> None:
    if _driver is None or not rows:
        return
    with _driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MERGE (e:Evidence {id: row.id})
            SET e.path = row.path,
                e.source = row.source,
                e.company = row.company,
                e.observed_at = row.observed_at,
                e.simhash = row.simhash
            """,
            rows=rows,
        )


def delete_evidence_many(ids: list[str]) -> None:
    if _driver is None or not ids:
        return
    with _driver.session() as session:
        session.run(
            "UNWIND $ids AS id MATCH (e:Evidence {id: id}) DETACH DELETE e",
            ids=ids,
        )


def get_public_job(job_id: str) -> dict | None:
    cypher = """
    MATCH (j:Job {id: $id})-[:IN_DOMAIN]->(d:Domain)
    WHERE (j.status IS NULL OR j.status <> 'candidate')
    RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
           j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id,
           coalesce(j.watching, []) AS watching
    """
    with _driver.session() as session:
        row = session.run(cypher, id=job_id).single()
    return dict(row) if row else None


def upsert_job(*, id: str, name: str, domain: str, status: str | None = None) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MERGE (j:Job {id: $id})
            SET j.name = $name, j.status = $status
            WITH j
            MATCH (d:Domain {id: $domain})
            MERGE (j)-[:IN_DOMAIN]->(d)
            """,
            id=id,
            name=name,
            domain=domain,
            status=status,
        )


def upsert_skill(skill: dict) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MERGE (s:Skill {id: $id})
            SET s.name = $name, s.synonyms = $synonyms
            """,
            id=skill["id"],
            name=skill["name"],
            synonyms=list(skill.get("synonyms") or []),
        )


def list_skills() -> list[dict]:
    if _driver is None:
        return []
    from app.llm.embed import embed

    with _driver.session() as session:
        rows = list(session.run("MATCH (s:Skill) RETURN s.id AS id, s.name AS name, s.synonyms AS synonyms"))
    out = []
    for row in rows:
        item = dict(row)
        item["synonyms"] = list(item.get("synonyms") or [])
        item["embedding"] = embed([item["name"]])[0]
        out.append(item)
    return out


def set_watching(job_id: str, skill_ids: list[str]) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            "MATCH (j:Job {id: $id}) SET j.watching = $ids",
            id=job_id,
            ids=skill_ids,
        )


def apply_requires(payload: dict) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MERGE (j:Job {id: $job_id})
            SET j.name = coalesce($job_name, j.name),
                j.status = CASE WHEN j.status = 'candidate' THEN null ELSE j.status END
            WITH j
            MATCH (d:Domain {id: $domain})
            MERGE (j)-[:IN_DOMAIN]->(d)
            MERGE (s:Skill {id: $skill_id})
            SET s.name = coalesce($skill_name, s.name)
            MERGE (j)-[r:REQUIRES]->(s)
            ON CREATE SET r.valid_from = datetime(), r.valid_to = null
            SET r.kind = $kind,
                r.proficiency = $proficiency,
                r.weight = $weight,
                r.levels = $levels,
                r.layer = $layer,
                r.confidence = $confidence,
                r.sources = $sources
            """,
            job_id=payload["job_id"],
            job_name=payload.get("job_name") or "",
            domain=payload.get("domain") or "ai",
            skill_id=payload["skill_id"],
            skill_name=payload.get("skill_name") or "",
            kind=payload.get("kind_edge") or "required",
            proficiency=payload.get("proficiency") or "able",
            weight=float(payload.get("weight") or 1),
            levels=payload.get("levels") or ["junior", "mid", "senior"],
            layer=payload.get("layer") or "low",
            confidence=float(payload.get("confidence") or 0),
            sources=list(payload.get("sources") or []),
        )
        watching = payload.get("watching")
        if watching:
            session.run(
                "MATCH (j:Job {id: $id}) SET j.watching = $ids",
                id=payload["job_id"],
                ids=watching,
            )


def list_requires(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (j:Job {id: $id})-[r:REQUIRES]->(s:Skill)
            WHERE r.valid_to IS NULL
            RETURN s.id AS skill_id, s.name AS name, r.kind AS kind,
                   r.proficiency AS proficiency, r.layer AS layer,
                   r.confidence AS confidence, r.sources AS sources,
                   r.levels AS levels, r.weight AS weight
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


def upsert_event(event: dict, job_id: str | None) -> None:
    if _driver is None:
        return
    payload = event.get("payload") or {}
    if not isinstance(payload, str):
        payload = json.dumps(payload, ensure_ascii=False)
    with _driver.session() as session:
        session.run(
            """
            MERGE (e:EvolutionEvent {id: $id})
            SET e.kind = $kind, e.at = $at, e.confidence = $confidence,
                e.review = $review, e.payload = $payload
            """,
            id=event["id"],
            kind=event.get("kind") or "",
            at=event.get("at") or "",
            confidence=float(event.get("confidence") or 0),
            review=event.get("review") or "pending",
            payload=payload,
        )
        if job_id:
            session.run(
                """
                MATCH (e:EvolutionEvent {id: $eid})
                MATCH (j:Job {id: $jid})
                MERGE (e)-[:AFFECTS]->(j)
                """,
                eid=event["id"],
                jid=job_id,
            )


def get_event(event_id: str) -> dict | None:
    if _driver is None:
        return None
    with _driver.session() as session:
        row = session.run(
            """
            MATCH (e:EvolutionEvent {id: $id})
            RETURN e.id AS id, e.kind AS kind, e.at AS at, e.confidence AS confidence,
                   e.review AS review, e.payload AS payload
            """,
            id=event_id,
        ).single()
    if row is None:
        return None
    data = dict(row)
    payload = data.get("payload") or "{}"
    if isinstance(payload, str):
        data["payload"] = json.loads(payload)
    return data


def list_pending_events() -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (e:EvolutionEvent)
            WHERE e.review = 'pending'
            RETURN e.id AS id, e.kind AS kind, e.at AS at, e.confidence AS confidence,
                   e.review AS review, e.payload AS payload
            ORDER BY e.at
            """
        )
        out = []
        for row in rows:
            data = dict(row)
            payload = data.get("payload") or "{}"
            if isinstance(payload, str):
                data["payload"] = json.loads(payload)
            out.append(data)
        return out



