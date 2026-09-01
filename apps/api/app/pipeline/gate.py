from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.collectors.normalize import is_channel_name, normalize_company
from app.collectors.sink import STREAM_KEY, connect_redis
from app.llm.embed import embed
from app.pipeline.align import align_job, align_skill, cluster_texts, split_composite
from app.pipeline.constants import (
    COVERAGE_THRESHOLD,
    DISCOVER_MIN_CLUSTER,
    EXTRACT_CACHE_VERSION,
    EXTRACT_WORKERS,
    PASSTHROUGH_KEY,
    SKILL_IRON_CATEGORY,
)
from app.pipeline.discover import classify_cluster
from app.pipeline.extract import ExtractedJd, parse_extracted
from app.pipeline.sections import section_of
from app.pipeline.status import is_target_job, job_id_for, refresh_job_status
from app.targets import JOB_TARGET_NAMES

_passthrough = False


def set_passthrough(enabled: bool) -> None:
    global _passthrough
    _passthrough = bool(enabled)
    try:
        connect_redis().set(PASSTHROUGH_KEY, "1" if enabled else "0")
    except Exception:
        pass


def passthrough_enabled() -> bool:
    try:
        value = connect_redis().get(PASSTHROUGH_KEY)
        if value is not None:
            return str(value) in ("1", "true", "True")
    except Exception:
        pass
    return _passthrough


def confidence_layer(*, excerpt: str, n_sources: int, extract_confidence: float) -> str:
    if not (excerpt or "").strip():
        return "low"
    if n_sources >= 3 and extract_confidence >= 0.8:
        return "high"
    if extract_confidence >= 0.5:
        return "mid"
    return "low"


def coverage(*, mentioned_in: int, cluster_size: int) -> float:
    if cluster_size <= 0:
        return 0.0
    return mentioned_in / cluster_size


def pool_skill(*, section: str, coverage_rate: float) -> bool:
    if section in ("benefit", "intro"):
        return False
    return coverage_rate >= COVERAGE_THRESHOLD


def _merge_category(members: list[tuple[str, str]]) -> str:
    for name, _ in members:
        iron = SKILL_IRON_CATEGORY.get((name or "").strip().casefold())
        if iron:
            return iron
    votes = [category for _, category in members if category]
    if not votes:
        return ""
    return Counter(votes).most_common(1)[0][0]


def _stable_id(prefix: str, name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


def _event_id(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return "evt-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def enqueue_extract_failure(snapshot: dict, error: str) -> dict:
    from app import graph

    payload = {
        "kind": "extract_failed",
        "path": snapshot.get("path"),
        "evidence_id": snapshot.get("id"),
        "error": error,
        "layer": "low",
    }
    event = {
        "id": _event_id(payload),
        "kind": "extract_failed",
        "at": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.0,
        "review": "pending",
        "payload": payload,
    }
    graph.upsert_event(event, job_id=None)
    _emit("review_enqueued", event)
    return event


def apply_event(event_id: str, *, review: str, payload: dict | None = None) -> dict:
    from app import graph

    event = graph.get_event(event_id)
    if event is None:
        raise KeyError(event_id)
    data = payload if payload is not None else event["payload"]
    if isinstance(data, str):
        data = json.loads(data)
    event["payload"] = data
    if data.get("layer") == "low" and review == "auto_passed":
        review = "pending"
    event["review"] = review
    if data.get("kind") != "extract_failed" and review in ("approved", "auto_passed"):
        graph.apply_requires(data)
    graph.upsert_event(event, job_id=data.get("job_id"))
    if data.get("job_id"):
        refresh_job_status(data["job_id"])
    return event


def _cache_file(snap: dict) -> Path | None:
    # 后缀用 .cache 而非 .json：避免被 select_snapshots 的 jd-*.json glob 当成 JD 表
    path = snap.get("path")
    if not path:
        return None
    return Path(f"{path}.extract-v{EXTRACT_CACHE_VERSION}.cache")


def _load_cached_extract(snap: dict) -> ExtractedJd | None:
    cache_file = _cache_file(snap)
    if cache_file is None:
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("v") != EXTRACT_CACHE_VERSION:
        return None
    try:
        return ExtractedJd.model_validate(data.get("extracted"))
    except ValidationError:
        return None


def _store_cached_extract(snap: dict, parsed: ExtractedJd) -> None:
    cache_file = _cache_file(snap)
    if cache_file is None:
        return
    try:
        cache_file.write_text(
            json.dumps(
                {"v": EXTRACT_CACHE_VERSION, "extracted": parsed.model_dump()},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass  # ponytail: 缓存尽力而为，写失败只损失一次加速，重跑即自愈


def run_extract_and_gate(
    snapshots: list[dict],
    complete_json=None,
    workers: int | None = None,
    cache: bool = False,
) -> list[dict]:
    from app import graph
    from app.llm.client import complete_json as default_complete

    graph.init_graph()
    graph.upsert_evidence_many(snapshots)
    complete = complete_json or default_complete
    n_workers = workers if workers is not None else (1 if complete_json else EXTRACT_WORKERS)
    n_workers = max(1, min(n_workers, max(1, len(snapshots))))

    def _extract_one(snap: dict):
        if cache:
            cached = _load_cached_extract(snap)
            if cached is not None:
                return ("ok", snap, cached)
        try:
            parsed = parse_extracted(complete, snapshot=snap)
        except ValueError as exc:
            return ("fail", snap, str(exc))
        if cache:
            _store_cached_extract(snap, parsed)
        return ("ok", snap, parsed)

    if n_workers == 1:
        extracted = [_extract_one(snap) for snap in snapshots]
    else:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            extracted = list(pool.map(_extract_one, snapshots))

    extracted_rows = []
    events: list[dict] = []
    for status, snap, payload in extracted:
        if status == "fail":
            events.append(enqueue_extract_failure(snap, payload))
            continue
        extracted_rows.append((snap, payload))

    aligned: dict[str, list] = defaultdict(list)
    unmatched: dict[str, list] = defaultdict(list)
    for snap, parsed in extracted_rows:
        # LLM 抽出的 target 不一定是规范名，先过靶子名单，非规范名走 align_job 消解；
        # 别名池快照一律不直连靶子（f26a666：近名批先聚类判别，防止误计独立源）
        raw = None if snap.get("alias_candidate") else (parsed.target or parsed.job_name)
        hit = raw if raw in JOB_TARGET_NAMES else align_job(raw)
        if hit:
            aligned[hit].append((snap, parsed, hit))
        else:
            unmatched[parsed.job_name].append((snap, parsed, parsed.job_name))

    index: list[dict] = graph.list_skills()
    for job_name, rows in aligned.items():
        events.extend(_gate_job(job_name, rows, index, judged="target"))
    events.extend(_discover_unmatched(unmatched, index, complete))
    return events


def _discover_unmatched(unmatched: dict[str, list], index: list[dict], complete) -> list[dict]:
    from app import graph

    events = []
    for title, rows in unmatched.items():
        if len(rows) < DISCOVER_MIN_CLUSTER:
            continue
        skills = []
        for _, parsed, _ in rows:
            skills.extend(s.name for s in parsed.skills)
        kind, alias_of = classify_cluster(title, skills, complete)
        if kind == "noise":
            continue
        if kind == "alias" and alias_of:
            source_id = job_id_for(title)
            target_id = job_id_for(alias_of)
            domain = rows[0][1].domain or rows[0][0].get("domain") or "ai"
            graph.upsert_job(id=source_id, name=title, domain=domain, status="candidate")
            graph.upsert_job(id=target_id, name=alias_of, domain=domain, status="candidate")
            graph.set_alias(source_id, target_id)
            graph.set_job_fields(source_id, judged="alias")
            events.extend(_gate_job(alias_of, rows, index, judged="target"))
            continue
        events.extend(_gate_job(title, rows, index, judged="new"))
    return events


def _gate_job(job_name: str, rows: list, index: list[dict], judged: str = "target") -> list[dict]:
    from app import graph

    job_id = job_id_for(job_name)
    domain = rows[0][1].domain or rows[0][0].get("domain") or "ai"
    graph.upsert_job(id=job_id, name=job_name, domain=domain, status="candidate")
    if judged == "new":
        graph.set_job_fields(job_id, judged="new")
    elif is_target_job(job_name):
        graph.set_job_fields(job_id, judged="target")
    for snap, _, _ in rows:
        graph.link_evidence(snap["id"], job_id)

    company_by_evidence = {
        snap["id"]: snap.get("company") or "" for snap, _, _ in rows
    }
    mentions: dict[str, dict] = {}
    cluster_size = len(rows)
    pending_names: list[tuple] = []

    for snap, parsed, _ in rows:
        for skill in parsed.skills:
            section = section_of(snap.get("body") or "", skill.excerpt)
            if not skill.excerpt:
                section = skill.section
            if section in ("benefit", "intro"):
                continue
            pending_names.append((snap, skill, section))

    # 并列串拆到条目级：C/C++ → C、C++ 两条，下游按名聚类/对齐/计覆盖
    expanded: list[tuple] = []
    for snap, sk, section in pending_names:
        for piece in split_composite(sk.name, index):
            expanded.append((snap, sk.model_copy(update={"name": piece}), section))

    names = [sk.name for _, sk, _ in expanded]
    clustered = cluster_texts(names) if names else []
    centroid_for = {}
    for group in clustered:
        centroid = max(group, key=len)
        for name in group:
            centroid_for[name] = (centroid, group)

    members_by_centroid: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for snap, skill, _ in expanded:
        centroid, _ = centroid_for.get(skill.name, (skill.name, [skill.name]))
        members_by_centroid[centroid].append((skill.name, skill.category or ""))
    category_for = {
        centroid: _merge_category(members) for centroid, members in members_by_centroid.items()
    }

    for snap, skill, section in expanded:
        centroid, group = centroid_for.get(skill.name, (skill.name, [skill.name]))
        hit = align_skill(centroid, index) or align_skill(skill.name, index)
        if hit is None:
            skill_id = _stable_id("skill-", centroid)
            hit = {
                "id": skill_id,
                "name": centroid,
                "synonyms": list(dict.fromkeys(group)),
                "embedding": embed([centroid])[0],
                "category": category_for.get(centroid, ""),
            }
            graph.upsert_skill(hit)
            index.append(hit)
        elif skill.name not in (hit.get("synonyms") or []) and skill.name != hit.get("name"):
            hit.setdefault("synonyms", []).append(skill.name)
            graph.upsert_skill(hit)
        rec = mentions.setdefault(
            hit["id"],
            {
                "skill": hit,
                "evidence": set(),
                "kind": skill.kind,
                "proficiency": skill.proficiency,
                "confidence": skill.confidence,
                "excerpt": skill.excerpt,
                "section": section,
                "category": category_for.get(centroid, ""),
            },
        )
        rec["evidence"].add(snap["id"])
        rec["confidence"] = max(rec["confidence"], skill.confidence)
        if skill.excerpt:
            rec["excerpt"] = skill.excerpt

    watching = []
    pooled = []
    for skill_id, rec in mentions.items():
        rate = coverage(mentioned_in=len(rec["evidence"]), cluster_size=cluster_size)
        if not pool_skill(section=rec["section"], coverage_rate=rate):
            watching.append(skill_id)
        else:
            pooled.append((skill_id, rec))
    events = []
    for skill_id, rec in pooled:
        companies = set()
        for eid in rec["evidence"]:
            company = normalize_company(company_by_evidence.get(eid, ""))
            if company and not is_channel_name(company):
                companies.add(company)
        layer = confidence_layer(
            excerpt=rec["excerpt"],
            n_sources=len(companies),
            extract_confidence=rec["confidence"],
        )
        payload = {
            "kind": "requires_add",
            "job_id": job_id,
            "job_name": job_name,
            "domain": domain,
            "skill_id": skill_id,
            "skill_name": rec["skill"]["name"],
            "category": rec["category"],
            "kind_edge": rec["kind"],
            "proficiency": rec["proficiency"],
            "layer": layer,
            "confidence": rec["confidence"],
            "sources": sorted(rec["evidence"]),
            "excerpt": rec["excerpt"],
            "watching": watching,
            "weight": 1.0,
            "levels": ["junior", "mid", "senior"],
            "valid_from": max(
                (
                    snap.get("observed_at") or ""
                    for snap, _, _ in rows
                    if snap["id"] in rec["evidence"]
                ),
                default="",
            ),
        }
        review = "pending"
        if passthrough_enabled() and layer in ("high", "mid"):
            review = "auto_passed"
        event = {
            "id": _event_id(payload),
            "kind": "requires_add",
            "at": datetime.now(timezone.utc).isoformat(),
            "confidence": rec["confidence"],
            "review": review,
            "payload": payload,
        }
        graph.upsert_event(event, job_id=job_id)
        _emit("review_enqueued", event)
        if review == "auto_passed":
            graph.apply_requires(payload)
        events.append(event)
    graph.set_watching(job_id, watching)
    keep = [skill_id for skill_id, _ in pooled]
    latest = max((snap.get("observed_at") or "" for snap, _, _ in rows), default="")
    # 不让一次没有达到覆盖率门槛的快照掏空当前岗的要求边。
    if keep:
        graph.expire_absent_requires(job_id, keep, latest)
    refresh_job_status(job_id)
    return events


def _emit(event_type: str, event: dict) -> None:
    try:
        redis = connect_redis()
        redis.xadd(
            STREAM_KEY,
            {
                "id": event["id"],
                "type": event_type,
                "payload": json.dumps(event.get("payload") or {}, ensure_ascii=False),
            },
        )
    except Exception:
        pass
