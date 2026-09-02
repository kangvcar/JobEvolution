import json
import os
import hashlib
from datetime import datetime

from neo4j import GraphDatabase

from app.pipeline.constants import SKILL_CATEGORIES
from app.pipeline.status import source_stats

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
    "CREATE CONSTRAINT requirement_version_id IF NOT EXISTS FOR (n:RequirementVersion) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT review_proposal_id IF NOT EXISTS FOR (n:ReviewProposal) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT skill_merge_id IF NOT EXISTS FOR (n:SkillMerge) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT review_decision_id IF NOT EXISTS FOR (n:ReviewDecision) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT job_definition_version_id IF NOT EXISTS FOR (n:JobDefinitionVersion) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT definition_claim_id IF NOT EXISTS FOR (n:DefinitionClaim) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT graph_release_id IF NOT EXISTS FOR (n:GraphRelease) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT graph_pointer_id IF NOT EXISTS FOR (n:GraphPointer) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX evolution_event_at IF NOT EXISTS FOR (n:EvolutionEvent) ON (n.at)",
)

_driver = None


def init_graph():
    global _driver
    if _driver is not None:
        return
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    driver = GraphDatabase.driver(
        uri,
        auth=(
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "jobevolution"),
        ),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:
        driver.close()
        hint = "（测试库先起：docker compose --profile test up -d neo4j-test）" if os.environ.get("NEO4J_TEST") == "1" else ""
        raise RuntimeError(f"Neo4j {uri} 连不上{hint}") from exc
    _driver = driver
    with _driver.session() as session:
        for statement in _CONSTRAINTS:
            session.run(statement)
        for domain in DOMAINS:
            session.run(
                "MERGE (n:Domain {id: $id}) SET n.name = $name",
                id=domain["id"],
                name=domain["name"],
            )
        for cid, cname in SKILL_CATEGORIES.items():
            session.run(
                "MERGE (n:SkillCategory {id: $id}) SET n.name = $name",
                id=cid,
                name=cname,
            )
        snapshot = os.environ.get("SNAPSHOT_PATH")
        if snapshot and os.path.exists(snapshot):
            count = session.run("MATCH (n:Job) RETURN count(n) AS n").single()["n"]
            if count == 0:
                from app.graph_snapshot import import_snapshot
                import_snapshot(snapshot)


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
WHERE j.status IN ['emerging', 'formed']
  AND ($domain IS NULL OR d.id = $domain)
  AND ($status IS NULL OR j.status = $status)
  AND ($q IS NULL OR toLower(j.name) CONTAINS toLower($q))
  AND ($category IS NULL OR EXISTS {
    MATCH (j)-[r:REQUIRES]->(s:Skill)-[:IN_CATEGORY]->(c:SkillCategory)
    WHERE r.valid_to IS NULL AND c.name = $category
  })
  AND ($level IS NULL OR EXISTS {
    MATCH (j)-[r:REQUIRES]->(s:Skill)
    WHERE r.valid_to IS NULL AND $level IN coalesce(r.levels, [])
  })
RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
       j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id
"""


def list_jobs(*, domain: str | None, status: str | None, q: str | None,
              category: str | None = None, level: str | None = None) -> list[dict]:
    if status == "candidate":
        return []
    with _driver.session() as session:
        return [
            dict(row)
            for row in session.run(
                _PUBLIC_JOB,
                domain=domain,
                status=status,
                q=q,
                category=category,
                level=level,
            )
        ]


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


def _job_row(job_id: str, *, public_only: bool) -> dict | None:
    extra = "AND j.status IN ['emerging', 'formed']" if public_only else ""
    cypher = f"""
    MATCH (j:Job {{id: $id}})-[:IN_DOMAIN]->(d:Domain)
    WHERE true {extra}
    RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
           j.code AS code, j.esco_id AS esco_id, j.onet_id AS onet_id,
           coalesce(j.watching, []) AS watching, coalesce(j.judged, '') AS judged
    """
    if _driver is None:
        return None
    with _driver.session() as session:
        row = session.run(cypher, id=job_id).single()
    return dict(row) if row else None


def get_public_job(job_id: str) -> dict | None:
    return _job_row(job_id, public_only=True)


def get_any_job(job_id: str) -> dict | None:
    return _job_row(job_id, public_only=False)


def upsert_job(*, id: str, name: str, domain: str, status: str | None = None) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MERGE (j:Job {id: $id})
            SET j.name = $name, j.status = $status
            WITH DISTINCT j
            OPTIONAL MATCH (j)-[:IN_DOMAIN]->(existing:Domain)
            WITH j, coalesce(existing.id, $domain) AS dom_id
            MATCH (d:Domain {id: dom_id})
            MERGE (j)-[:IN_DOMAIN]->(d)
            """,
            id=id,
            name=name,
            domain=domain,
            status=status,
        )


def _link_skill_category(session, skill_id: str, category: str) -> None:
    if category not in SKILL_CATEGORIES:
        return
    session.run(
        """
        MATCH (s:Skill {id: $id})
        OPTIONAL MATCH (s)-[old:IN_CATEGORY]->(:SkillCategory)
        DELETE old
        MERGE (c:SkillCategory {id: $category})
        SET c.name = $category_name
        MERGE (s)-[:IN_CATEGORY]->(c)
        """,
        id=skill_id,
        category=category,
        category_name=SKILL_CATEGORIES[category],
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
        _link_skill_category(session, skill["id"], skill.get("category") or "")


def apply_skill_merge(payload: dict) -> None:
    """Apply a reviewed merge while retaining the old Skill node and its IDs."""
    if _driver is None:
        return
    old_id = str(payload.get("old_skill_id") or "")
    canonical_id = str(payload.get("canonical_skill_id") or "")
    proposed_name = str(payload.get("proposed_name") or "").strip()
    if not old_id or not canonical_id or old_id == canonical_id:
        return
    merge_id = f"merge-{old_id}-{canonical_id}"
    with _driver.session() as session:
        session.run(
            """
            MATCH (old:Skill {id: $old_id}), (canonical:Skill {id: $canonical_id})
            SET old.merged_into = $canonical_id
            SET canonical.synonyms = CASE
                WHEN $proposed_name = '' THEN coalesce(canonical.synonyms, [])
                WHEN $proposed_name IN coalesce(canonical.synonyms, []) THEN canonical.synonyms
                ELSE coalesce(canonical.synonyms, []) + $proposed_name
            END
            MERGE (m:SkillMerge {id: $merge_id})
            SET m.old_skill_id = $old_id, m.canonical_skill_id = $canonical_id,
                m.proposed_name = $proposed_name, m.approved_at = datetime()
            MERGE (old)-[:MERGED_INTO]->(canonical)
            """,
            old_id=old_id,
            canonical_id=canonical_id,
            proposed_name=proposed_name,
            merge_id=merge_id,
        )


def list_skills(*, with_embed: bool = True) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = list(session.run("MATCH (s:Skill) RETURN s.id AS id, s.name AS name, s.synonyms AS synonyms, s.merged_into AS merged_into"))
    out = [dict(row) for row in rows]
    for item in out:
        item["synonyms"] = list(item.get("synonyms") or [])
    if with_embed and out:
        # ponytail: 每次调用整表重算嵌入；远端 bge-m3 后单请求约 3s，向太多时在 Skill 节点上落 embedding 属性
        from app.llm.embed import embed

        vectors = embed([item["name"] for item in out])
        for item, vec in zip(out, vectors, strict=True):
            item["embedding"] = vec
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
        valid_from = payload.get("valid_from") or datetime.now().isoformat()
        # Business fields define identity; evidence can change without creating a new fact.
        signature_payload = {
            key: payload.get(key)
            for key in ("job_id", "skill_id", "kind_edge", "proficiency", "weight", "levels", "layer", "group_id", "min_required")
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        session.run(
            "MERGE (j:Job {id: $job_id}) SET j.name = coalesce($job_name, j.name) "
            "MERGE (s:Skill {id: $skill_id}) SET s.name = coalesce($skill_name, s.name)",
            job_id=payload["job_id"], job_name=payload.get("job_name") or "",
            skill_id=payload["skill_id"], skill_name=payload.get("skill_name") or "",
        )
        version_id = f"reqv-{payload['job_id']}-{payload['skill_id']}-{signature}"
        session.run(
            """
            MATCH (j:Job {id: $job_id})
            OPTIONAL MATCH (j)-[old:REQUIRES_VERSION {active: true}]->(previous:RequirementVersion)
            WHERE previous.skill_id = $skill_id AND previous.signature <> $signature
            SET old.active = false, previous.valid_to = datetime($valid_from)
            """,
            job_id=payload["job_id"], skill_id=payload["skill_id"], signature=signature, valid_from=valid_from,
        )
        session.run(
            """
            MERGE (v:RequirementVersion {id: $id})
            ON CREATE SET v.created_at = datetime($valid_from), v.valid_from = datetime($valid_from)
            SET v.signature = $signature, v.job_id = $job_id, v.skill_id = $skill_id,
                v.kind = $kind, v.proficiency = $proficiency, v.weight = $weight,
                v.levels = $levels, v.layer = $layer, v.confidence = $confidence,
                v.valid_to = null, v.sources = $sources, v.excerpt = $excerpt
            WITH v
            MATCH (j:Job {id: $job_id})
            MATCH (s:Skill {id: $skill_id})
            MERGE (j)-[rv:REQUIRES_VERSION {id: $id}]->(v)
            SET rv.active = true
            MERGE (v)-[:FOR_SKILL]->(s)
            FOREACH (_ IN CASE WHEN $group_id IS NULL THEN [] ELSE [1] END |
                MERGE (g:RequirementGroup {id: $group_id})
                SET g.min_required = $min_required
                MERGE (v)-[:IN_GROUP]->(g))
            """,
            id=version_id,
            signature=signature,
            job_id=payload["job_id"],
            skill_id=payload["skill_id"],
            kind=payload.get("kind_edge") or "required",
            proficiency=payload.get("proficiency") or "able",
            weight=float(payload.get("weight") or 1),
            levels=payload.get("levels") or ["junior", "mid", "senior"],
            layer=payload.get("layer") or "low",
            confidence=float(payload.get("confidence") or 0),
            sources=list(payload.get("sources") or []),
            excerpt=payload.get("excerpt") or "",
            valid_from=valid_from,
            group_id=payload.get("group_id"), min_required=int(payload.get("min_required") or 1),
        )
        session.run(
            """
            MERGE (j:Job {id: $job_id})
            SET j.name = coalesce($job_name, j.name)
            WITH DISTINCT j
            OPTIONAL MATCH (j)-[:IN_DOMAIN]->(existing:Domain)
            WITH j, coalesce(existing.id, $domain) AS dom_id
            MATCH (d:Domain {id: dom_id})
            MERGE (j)-[:IN_DOMAIN]->(d)
            MERGE (s:Skill {id: $skill_id})
            SET s.name = coalesce($skill_name, s.name)
            MERGE (j)-[r:REQUIRES]->(s)
            ON CREATE SET r.valid_from = datetime($valid_from), r.valid_to = null
            SET r.kind = $kind,
                r.proficiency = $proficiency,
                r.weight = $weight,
                r.levels = $levels,
                r.layer = $layer,
                r.confidence = $confidence,
                r.sources = $sources,
                r.excerpt = $excerpt,
                r.valid_to = null
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
            excerpt=payload.get("excerpt") or "",
            valid_from=payload.get("valid_from") or datetime.now().isoformat(),
        )
        evidence_ids = list(payload.get("sources") or [])
        if evidence_ids:
            session.run(
                """
                MATCH (v:RequirementVersion {id: $id})
                UNWIND $evidence_ids AS evidence_id
                MATCH (e:Evidence {id: evidence_id})
                MERGE (v)-[:SUPPORTED_BY]->(e)
                """,
                id=version_id,
                evidence_ids=evidence_ids,
            )
        watching = payload.get("watching")
        if watching:
            session.run(
                "MATCH (j:Job {id: $id}) SET j.watching = $ids",
                id=payload["job_id"],
                ids=watching,
            )
        _link_skill_category(session, payload["skill_id"], payload.get("category") or "")


def list_requires(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (j:Job {id: $id})-[:REQUIRES_VERSION {active: true}]->(v:RequirementVersion)-[:FOR_SKILL]->(s:Skill)
            WHERE coalesce(v.retracted, false) = false
              AND NOT EXISTS { MATCH (v)-[:SUPPORTED_BY]->(retracted:Evidence) WHERE retracted.retracted = true }
            OPTIONAL MATCH (s)-[:IN_CATEGORY]->(c:SkillCategory)
            OPTIONAL MATCH (v)-[:IN_GROUP]->(g:RequirementGroup)
            OPTIONAL MATCH (v)-[:SUPPORTED_BY]->(e:Evidence)
            WITH s, v, c, g, collect(e.id) AS evidence_ids
            RETURN s.id AS skill_id, s.name AS name, v.kind AS kind,
                   c.id AS category_id, c.name AS category,
                   v.proficiency AS proficiency, v.layer AS layer,
                   v.confidence AS confidence, coalesce(v.sources, evidence_ids) AS sources,
                   v.levels AS levels, v.weight AS weight,
                   coalesce(v.excerpt, '') AS excerpt,
                   g.id AS group_id, g.min_required AS min_required,
                   toString(v.valid_from) AS valid_from, toString(v.valid_to) AS valid_to
            """,
            id=job_id,
        )
        out = [dict(row) for row in rows]
        if not out:
            rows = session.run(
                """
            MATCH (j:Job {id: $id})-[r:REQUIRES]->(s:Skill)
            WHERE r.valid_to IS NULL AND coalesce(r.retracted, false) = false
            OPTIONAL MATCH (s)-[:IN_CATEGORY]->(c:SkillCategory)
            RETURN s.id AS skill_id, s.name AS name, r.kind AS kind,
                   c.id AS category_id, c.name AS category,
                   r.proficiency AS proficiency, r.layer AS layer,
                   r.confidence AS confidence, r.sources AS sources,
                   r.levels AS levels, r.weight AS weight,
                   coalesce(r.excerpt, '') AS excerpt,
                   null AS group_id, 1 AS min_required,
                   toString(r.valid_from) AS valid_from, toString(r.valid_to) AS valid_to
            """,
            id=job_id,
            )
            out = [dict(row) for row in rows]
    if any(not (row.get("excerpt") or "").strip() for row in out):
        by_skill: dict[str, str] = {}
        for event in list_job_events(job_id):
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            sid = payload.get("skill_id")
            excerpt = (payload.get("excerpt") or "").strip()
            if sid and excerpt:
                by_skill[sid] = excerpt
        for row in out:
            if not (row.get("excerpt") or "").strip():
                row["excerpt"] = by_skill.get(row["skill_id"]) or ""
    return out


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
        session.run(
            """
            MERGE (p:ReviewProposal {id: $id})
            ON CREATE SET p.event_id = $id, p.payload = $payload, p.created_at = datetime($at),
                          p.model = $model, p.prompt = $prompt, p.confidence = $confidence
            WITH p
            MATCH (e:EvolutionEvent {id: $id})
            MERGE (p)-[:FOR_EVENT]->(e)
            """,
            id=event["id"], payload=payload, at=event.get("at") or datetime.now().isoformat(),
            model=event.get("model") or "", prompt=event.get("prompt") or "",
            confidence=float(event.get("confidence") or 0),
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


def record_review_decision(event_id: str, *, review: str, payload: dict, reason: str = "") -> str | None:
    if _driver is None:
        return None
    raw = json.dumps({"event_id": event_id, "review": review, "payload": payload, "reason": reason}, ensure_ascii=False, sort_keys=True)
    decision_id = "decision-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    with _driver.session() as session:
        session.run(
            """
            MERGE (d:ReviewDecision {id: $id})
            ON CREATE SET d.event_id = $event_id, d.review = $review, d.payload = $payload,
                          d.reason = $reason, d.decided_at = datetime()
            WITH d
            MATCH (p:ReviewProposal {id: $event_id})
            MERGE (p)-[:HAS_DECISION]->(d)
            """,
            id=decision_id, event_id=event_id, review=review,
            payload=json.dumps(payload, ensure_ascii=False), reason=reason,
        )
    return decision_id


def apply_definition_claims(job_id: str, claims: list[dict], *, event_id: str) -> None:
    if _driver is None or not claims:
        return
    version_id = "defv-" + hashlib.sha256(f"{job_id}:{event_id}".encode()).hexdigest()[:24]
    with _driver.session() as session:
        session.run(
            "MERGE (v:JobDefinitionVersion {id: $id}) ON CREATE SET v.job_id = $job_id, v.created_at = datetime(), v.status = 'approved' "
            "WITH v MATCH (j:Job {id: $job_id}) MERGE (j)-[:HAS_DEFINITION]->(v)",
            id=version_id, job_id=job_id,
        )
        for claim in claims:
            if not isinstance(claim, dict) or not claim.get("text"):
                continue
            claim_id = "claim-" + hashlib.sha256(json.dumps(claim, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
            claim_type = claim.get("type") or "responsibility"
            sources = sorted({str(source) for source in claim.get("sources") or [] if source})
            session.run(
                """
                MERGE (c:DefinitionClaim {id: $id})
                ON CREATE SET c.text = $text, c.type = $type, c.sources = $sources, c.review = 'approved'
                WITH c MATCH (v:JobDefinitionVersion {id: $version_id}) MERGE (v)-[:HAS_CLAIM]->(c)
                """,
                id=claim_id, text=str(claim["text"]), type=claim_type, sources=sources, version_id=version_id,
            )


def current_definition(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            "MATCH (j:Job {id: $id})-[:HAS_DEFINITION]->(v:JobDefinitionVersion {status: 'approved'})-[:HAS_CLAIM]->(c:DefinitionClaim) "
            "RETURN c.id AS id, c.text AS text, c.type AS type, c.sources AS sources ORDER BY c.type, c.id",
            id=job_id,
        )
        return [dict(row) for row in rows]


def publish_graph_release(*, period: str = "", metadata: dict | None = None) -> dict:
    """Create an immutable release and atomically move the public pointer."""
    if _driver is None:
        return {}
    stamp = datetime.now().isoformat()
    raw = json.dumps({"period": period, "metadata": metadata or {}, "at": stamp}, ensure_ascii=False, sort_keys=True)
    release_id = "release-" + hashlib.sha256(raw.encode()).hexdigest()[:24]
    with _driver.session() as session:
        session.run(
            """
            MERGE (r:GraphRelease {id: $id})
            ON CREATE SET r.period = $period, r.metadata = $metadata, r.created_at = datetime($at), r.status = 'ready'
            MERGE (p:GraphPointer {id: 'public'})
            SET p.release_id = $id, p.updated_at = datetime($at)
            """,
            id=release_id, period=period, metadata=json.dumps(metadata or {}, ensure_ascii=False), at=stamp,
        )
    return {"id": release_id, "period": period, "published_at": stamp}


def rollback_graph_release(release_id: str) -> dict | None:
    if _driver is None:
        return None
    with _driver.session() as session:
        row = session.run("MATCH (r:GraphRelease {id: $id}) RETURN r.id AS id, r.period AS period", id=release_id).single()
        if not row:
            return None
        session.run("MERGE (p:GraphPointer {id: 'public'}) SET p.release_id = $id, p.updated_at = datetime()", id=release_id)
        return dict(row)


def public_release() -> dict:
    if _driver is None:
        return {"id": None, "period": "", "published_at": None}
    with _driver.session() as session:
        row = session.run(
            "MATCH (p:GraphPointer {id: 'public'}) OPTIONAL MATCH (r:GraphRelease {id: p.release_id}) RETURN p.release_id AS id, r.period AS period, toString(r.created_at) AS published_at"
        ).single()
    return dict(row) if row else {"id": None, "period": "", "published_at": None}


def list_pending_events(*, include_auto_passed: bool = False) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (e:EvolutionEvent)
            WHERE e.review = 'pending' OR ($include_auto_passed AND e.review = 'auto_passed')
            RETURN e.id AS id, e.kind AS kind, e.at AS at, e.confidence AS confidence,
                   e.review AS review, e.payload AS payload
            ORDER BY e.at
            """,
            include_auto_passed=include_auto_passed,
        )
        out = []
        for row in rows:
            data = dict(row)
            payload = data.get("payload") or "{}"
            if isinstance(payload, str):
                data["payload"] = json.loads(payload)
            out.append(data)
        return out


def link_evidence(evidence_id: str, job_id: str) -> None:
    if _driver is None or not evidence_id or not job_id:
        return
    with _driver.session() as session:
        session.run(
            """
            MATCH (e:Evidence {id: $eid})
            MATCH (j:Job {id: $jid})
            MERGE (e)-[:FOR]->(j)
            """,
            eid=evidence_id,
            jid=job_id,
        )


def list_job_evidence(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (e:Evidence)-[:FOR]->(j:Job {id: $id})
            WHERE coalesce(e.retracted, false) = false
            RETURN e.company AS company, e.observed_at AS observed_at,
                   e.id AS id, e.source AS source
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


def retract_event(event_id: str, reason: str) -> dict | None:
    event = get_event(event_id)
    if event is None or _driver is None:
        return None
    payload = event.get("payload") or {}
    with _driver.session() as session:
        session.run("MATCH (e:EvolutionEvent {id: $id}) SET e.review = 'retracted', e.retraction_reason = $reason, e.retracted_at = datetime()", id=event_id, reason=reason)
        if payload.get("job_id") and payload.get("skill_id"):
            session.run(
                """
                MATCH (j:Job {id: $job_id})-[r:REQUIRES]->(s:Skill {id: $skill_id})
                SET r.retracted = true, r.valid_to = datetime()
                WITH j, s
                MATCH (j)-[:REQUIRES_VERSION]->(v:RequirementVersion)-[:FOR_SKILL]->(s)
                SET v.retracted = true, v.valid_to = datetime()
                """, job_id=payload["job_id"], skill_id=payload["skill_id"]
            )
    return {**event, "review": "retracted", "reason": reason}


def retract_evidence(evidence_id: str, reason: str) -> bool:
    if _driver is None:
        return False
    with _driver.session() as session:
        row = session.run("MATCH (e:Evidence {id: $id}) SET e.retracted = true, e.retraction_reason = $reason, e.retracted_at = datetime() RETURN e.id AS id", id=evidence_id, reason=reason).single()
    return bool(row)


def set_alias(source_id: str, target_id: str) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MATCH (src:Job {id: $src})
            MATCH (dst:Job {id: $dst})
            MERGE (src)-[:ALIAS_OF]->(dst)
            """,
            src=source_id,
            dst=target_id,
        )


def has_alias_out(job_id: str) -> bool:
    if _driver is None:
        return False
    with _driver.session() as session:
        row = session.run(
            "MATCH (j:Job {id: $id})-[:ALIAS_OF]->() RETURN count(*) AS n",
            id=job_id,
        ).single()
    return bool(row and row["n"])


def definition_passed(job_id: str) -> bool:
    if _driver is None:
        return False
    with _driver.session() as session:
        defined = session.run(
            "MATCH (j:Job {id: $id})-[:HAS_DEFINITION]->(v:JobDefinitionVersion) RETURN count(v) AS n", id=job_id
        ).single()
        if defined and defined["n"]:
            row = session.run(
                "MATCH (j:Job {id: $id})-[:HAS_DEFINITION]->(v:JobDefinitionVersion {status: 'approved'})-[:HAS_CLAIM]->(c:DefinitionClaim) "
                "WITH collect(c) AS claims RETURN all(c IN claims WHERE (c.type = 'responsibility' AND size(coalesce(c.sources, [])) >= 2) OR (c.type = 'scenario' AND size(coalesce(c.sources, [])) >= 1)) AND size(claims) > 0 AS ok",
                id=job_id,
            ).single()
            return bool(row and row["ok"])
        row = session.run(
            """
            MATCH (e:EvolutionEvent)-[:AFFECTS]->(j:Job {id: $id})
            WHERE e.review IN ['approved', 'auto_passed']
            RETURN count(*) AS n
            """,
            id=job_id,
        ).single()
    return bool(row and row["n"])


def set_job_fields(job_id: str, **fields) -> None:
    if _driver is None or not fields:
        return
    sets = ", ".join(f"j.{key} = ${key}" for key in fields)
    params = {"id": job_id, **fields}
    with _driver.session() as session:
        session.run(f"MATCH (j:Job {{id: $id}}) SET {sets}", **params)


def expire_absent_requires(job_id: str, keep_ids: list[str], at_iso: str) -> None:
    if _driver is None:
        return
    with _driver.session() as session:
        session.run(
            """
            MATCH (j:Job {id: $id})-[r:REQUIRES]->(s:Skill)
            WHERE r.valid_to IS NULL
              AND NOT s.id IN $keep
              AND (r.valid_from IS NULL OR r.valid_from <= datetime($at))
            SET r.valid_to = datetime($at)
            """,
            id=job_id,
            keep=keep_ids,
            at=at_iso or datetime.now().isoformat(),
        )


def list_requires_history(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (j:Job {id: $id})-[r:REQUIRES]->(s:Skill)
            OPTIONAL MATCH (s)-[:IN_CATEGORY]->(c:SkillCategory)
            RETURN s.id AS skill_id, s.name AS name,
                   c.id AS category_id, c.name AS category,
                   toString(r.valid_from) AS valid_from,
                   toString(r.valid_to) AS valid_to,
                   r.layer AS layer, coalesce(r.retracted, false) AS retracted
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


def period_delta(job_id: str) -> dict:
    rows = list_requires_history(job_id)
    stamps = [
        (row.get("valid_from") or "")[:10]
        for row in rows
        if row.get("valid_from") or row.get("valid_to")
    ] + [(row.get("valid_to") or "")[:10] for row in rows if row.get("valid_to")]
    latest = max(stamps) if stamps else datetime.now().strftime("%Y-%m-%d")
    start = f"{latest[:4]}-01-01"
    added, expired = [], []
    for row in rows:
        if row.get("retracted"):
            continue
        valid_from = row.get("valid_from") or ""
        valid_to = row.get("valid_to") or ""
        item = {
            "skill_id": row["skill_id"],
            "name": row["name"],
            "category_id": row.get("category_id"),
            "category": row.get("category"),
        }
        if valid_to and valid_to[:10] >= start:
            expired.append(item)
        elif (not valid_to) and valid_from[:10] >= start:
            added.append(item)
    return {"added": added, "expired": expired}


def list_job_events(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (e:EvolutionEvent)-[:AFFECTS]->(j:Job {id: $id})
            RETURN e.id AS id, e.kind AS kind, e.at AS at, e.review AS review,
                   e.payload AS payload
            ORDER BY e.at
            """,
            id=job_id,
        )
        out = []
        for row in rows:
            data = dict(row)
            payload = data.get("payload") or "{}"
            if isinstance(payload, str):
                data["payload"] = json.loads(payload)
            out.append(data)
        return out


FORMED_SLICE = 3
_STORY_DISCOVER = "Agent 工程师"
_STORY_UPDATE = "大模型应用工程师"


def list_aliases_in(job_id: str) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (src:Job)-[:ALIAS_OF]->(dst:Job {id: $id})
            RETURN src.id AS id, src.name AS name
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


def alias_of(job_id: str) -> dict | None:
    if _driver is None:
        return None
    with _driver.session() as session:
        row = session.run(
            """
            MATCH (j:Job {id: $id})-[:ALIAS_OF]->(dst:Job)
            RETURN dst.id AS id, dst.name AS name
            """,
            id=job_id,
        ).single()
    return dict(row) if row else None


def _board_item(row: dict) -> dict:
    evidence = [
        ev
        for ev in (row.get("evidence") or [])
        if ev and ev.get("company")
    ]
    _, n_total, _ = source_stats(evidence)
    return {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"] or "candidate",
        "domain": row["domain"],
        "n_sources": n_total,
    }


def list_board_jobs() -> dict:
    empty = {"candidate": [], "emerging": [], "formed": []}
    if _driver is None:
        return empty
    with _driver.session() as session:
        rows = list(
            session.run(
                """
                MATCH (j:Job)-[:IN_DOMAIN]->(d:Domain)
                OPTIONAL MATCH (j)-[a:ALIAS_OF]->()
                WITH j, d, count(a) AS aliases
                OPTIONAL MATCH (e:Evidence)-[:FOR]->(j)
                RETURN j.id AS id, j.name AS name, j.status AS status, d.id AS domain,
                       aliases,
                       collect({company: e.company, observed_at: e.observed_at}) AS evidence
                """
            )
        )
    boards = {"candidate": [], "emerging": [], "formed": []}
    for row in rows:
        status = row["status"] or "candidate"
        if status == "candidate" and row["aliases"]:
            continue
        if status in boards:
            boards[status].append(_board_item(row))
    return boards


def _rank_formed(items: list[dict]) -> list[dict]:
    scored = []
    for item in items:
        delta = period_delta(item["id"])
        n = len(delta["added"]) + len(delta["expired"])
        prefer = 1 if item["name"] == _STORY_UPDATE else 0
        scored.append((prefer, n, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in scored]


def discover_boards() -> dict:
    boards = list_board_jobs()
    formed = _rank_formed(boards["formed"])
    return {
        "candidate": boards["candidate"],
        "emerging": boards["emerging"],
        "formed": formed[:FORMED_SLICE],
        "formed_total": len(formed),
    }


def discover_dossier(job_id: str) -> dict | None:
    job = get_any_job(job_id)
    if job is None:
        return None
    evidence = list_job_evidence(job_id)
    n_window, n_total, _ = source_stats(evidence)
    companies = []
    seen = set()
    for row in evidence:
        name = (row.get("company") or "").strip()
        if name and name not in seen:
            seen.add(name)
            companies.append(name)
    return {
        **job,
        "n_sources": n_total,
        "n_window": n_window,
        "cluster": {"n": len(evidence), "n_sources": n_total},
        "sources": companies,
        "evidence": evidence,
        "events": list_job_events(job_id),
        "aliases_in": list_aliases_in(job_id),
        "alias_of": alias_of(job_id),
    }


def _pick_named(items: list[dict], name: str) -> dict | None:
    for item in items:
        if item["name"] == name:
            return item
    return items[0] if items else None


def _story(kind: str, job: dict) -> dict:
    evidence = list_job_evidence(job["id"])
    _, n_total, _ = source_stats(evidence)
    delta = period_delta(job["id"])
    added = [row["name"] for row in delta["added"]]
    expired = [row["name"] for row in delta["expired"]]
    companies = []
    seen = set()
    for row in evidence:
        name = (row.get("company") or "").strip()
        if name and name not in seen:
            seen.add(name)
            companies.append(name)
    if kind == "discover":
        title = f"{job['name']}刚跨过萌芽线"
        hint = f"{n_total} 个独立源。判别是新岗位，不是别名。"
    else:
        extra = f" +{added[0]}" if added else ""
        title = f"{job['name']}{extra}"
        bits = []
        if added:
            bits.append("本周期有新增要求边")
        if expired:
            bits.append("已写 valid_to")
        hint = "，".join(bits) or "本周期切片差分"
    return {
        "kind": kind,
        "job_id": job["id"],
        "name": job["name"],
        "status": job["status"],
        "title": title,
        "hint": hint,
        "delta": [{"add": True, "name": name} for name in added]
        + [{"add": False, "name": name} for name in expired],
        "sources": " · ".join(companies[:8]),
        "n_sources": n_total,
    }


def _pipeline_counts() -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            "MATCH (e:Evidence) RETURN e.source AS source, count(*) AS n ORDER BY n DESC"
        )
        return [{"source": row["source"] or "local", "n": int(row["n"])} for row in rows]


def _heat(n_public: int) -> list[dict]:
    # ponytail: 谱内岗位占比, not 簇内覆盖率; persist coverage on REQUIRES if pt 12→33 is needed
    if _driver is None or n_public <= 0:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (j:Job)-[r:REQUIRES]->(s:Skill)
            WHERE j.status IN ['emerging', 'formed'] AND r.valid_to IS NULL
            RETURN s.id AS id, s.name AS name, count(DISTINCT j) AS n
            ORDER BY n DESC
            """
        )
        out = []
        for row in rows:
            v = round(100 * int(row["n"]) / n_public)
            out.append({"id": row["id"], "name": row["name"], "v": v})
        return out


def _move_lists(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    # ponytail: names from period_delta only; coverage-pt needs stored cluster rates
    rise, fall = [], []
    seen_r, seen_f = set(), set()
    for job in jobs:
        delta = period_delta(job["id"])
        for row in delta["added"]:
            if row["name"] not in seen_r:
                seen_r.add(row["name"])
                rise.append({"name": row["name"]})
        for row in delta["expired"]:
            if row["name"] not in seen_f:
                seen_f.add(row["name"])
                fall.append({"name": row["name"]})
    return rise, fall


def _feed_events() -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = session.run(
            """
            MATCH (e:EvolutionEvent)
            OPTIONAL MATCH (e)-[:AFFECTS]->(j:Job)
            RETURN e.kind AS kind, e.at AS at, e.review AS review,
                   e.payload AS payload, j.name AS job_name
            ORDER BY e.at DESC
            LIMIT 24
            """
        )
        out = []
        for row in rows:
            payload = row["payload"] or "{}"
            if isinstance(payload, str):
                payload = json.loads(payload)
            job_name = row["job_name"] or payload.get("job_name") or ""
            skill = payload.get("skill_name") or ""
            kind = row["kind"] or ""
            if kind == "requires_add" and skill:
                text = f"{job_name} +{skill}".strip()
            elif kind == "extract_failed":
                text = "抽取失败，拦下"
            elif kind == "job_status":
                text = f"{job_name} 状态流转".strip()
            else:
                text = f"{job_name} {kind}".strip()
            review = row["review"] or ""
            review_zh = {
                "pending": "待审",
                "approved": "已入谱",
                "auto_passed": "自动通过",
                "rejected": "驳回",
            }.get(review, review)
            out.append(
                {
                    "at": row["at"] or "",
                    "text": text,
                    "review": review_zh,
                    "kind": kind,
                }
            )
        return out


def build_feed() -> dict:
    boards = list_board_jobs()
    public = boards["emerging"] + boards["formed"]
    stories = []
    discover = _pick_named(boards["emerging"], _STORY_DISCOVER)
    if discover:
        stories.append(_story("discover", discover))
    update = _pick_named(boards["formed"], _STORY_UPDATE)
    if update:
        stories.append(_story("update", update))
    pending = len(list_pending_events())
    barred = 0
    if _driver is not None:
        with _driver.session() as session:
            row = session.run(
                "MATCH (e:EvolutionEvent {kind: 'extract_failed'}) RETURN count(*) AS n"
            ).single()
            barred = int(row["n"]) if row else 0
    rise, fall = _move_lists(public)
    return {
        "emerging": len(boards["emerging"]),
        "in_graph": len(public),
        "candidate": len(boards["candidate"]),
        "formed": len(boards["formed"]),
        "stories": stories,
        "pipeline": _pipeline_counts(),
        "heat": _heat(len(public)),
        "events": _feed_events(),
        "rise": rise,
        "fall": fall,
        "pending": pending,
        "barred": barred,
    }
