import json
import os
from datetime import datetime

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


def list_skills(*, with_embed: bool = True) -> list[dict]:
    if _driver is None:
        return []
    with _driver.session() as session:
        rows = list(session.run("MATCH (s:Skill) RETURN s.id AS id, s.name AS name, s.synonyms AS synonyms"))
    out = []
    embed_fn = None
    if with_embed:
        from app.llm.embed import embed

        embed_fn = embed
    for row in rows:
        item = dict(row)
        item["synonyms"] = list(item.get("synonyms") or [])
        if embed_fn is not None:
            item["embedding"] = embed_fn([item["name"]])[0]
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
            SET j.name = coalesce($job_name, j.name)
            WITH j
            MATCH (d:Domain {id: $domain})
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
            OPTIONAL MATCH (s)-[:IN_CATEGORY]->(c:SkillCategory)
            RETURN s.id AS skill_id, s.name AS name, r.kind AS kind,
                   c.id AS category_id, c.name AS category,
                   r.proficiency AS proficiency, r.layer AS layer,
                   r.confidence AS confidence, r.sources AS sources,
                   r.levels AS levels, r.weight AS weight,
                   coalesce(r.excerpt, '') AS excerpt,
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
            RETURN e.company AS company, e.observed_at AS observed_at,
                   e.id AS id, e.source AS source
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


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
            WHERE r.valid_to IS NULL AND NOT s.id IN $keep
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
                   r.layer AS layer
            """,
            id=job_id,
        )
        return [dict(row) for row in rows]


def period_delta(job_id: str, period_start: str | None = None) -> dict:
    rows = list_requires_history(job_id)
    if period_start is None:
        stamps = [
            (row.get("valid_from") or "")[:10]
            for row in rows
            if row.get("valid_from") or row.get("valid_to")
        ] + [(row.get("valid_to") or "")[:10] for row in rows if row.get("valid_to")]
        latest = max(stamps) if stamps else datetime.now().strftime("%Y-%m-%d")
        period_start = f"{latest[:4]}-01-01"
    start = period_start
    added, promoted, expired = [], [], []
    for row in rows:
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
    return {"added": added, "promoted": promoted, "expired": expired}


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


def _source_stats(rows: list[dict]) -> tuple[int, int, int]:
    from app.pipeline.status import source_stats

    return source_stats(rows)


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
    _, n_total, _ = _source_stats(evidence)
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
        n = len(delta["added"]) + len(delta["promoted"]) + len(delta["expired"])
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
    n_window, n_total, _ = _source_stats(evidence)
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
    _, n_total, _ = _source_stats(evidence)
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

