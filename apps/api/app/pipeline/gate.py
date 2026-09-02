from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.collectors.normalize import is_channel_name, normalize_company
from app.collectors.sink import STREAM_KEY, connect_redis
from app.llm.embed import embed
from app.pipeline.align import align_job, align_skill, nearest_skill, normalize_surface, split_composite, surface_clusters
from app.pipeline.constants import (
    COVERAGE_THRESHOLD,
    DISCOVER_MIN_CLUSTER,
    EXTRACT_CACHE_VERSION,
    EXTRACT_WORKERS,
    PASSTHROUGH_KEY,
    SKILL_IRON_CATEGORY,
)
from app.pipeline.discover import classify_cluster
from app.pipeline.extract import (
    ExtractedJd,
    brand_action_skill,
    classify_skill_candidate,
    parse_extracted,
)
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


def automatic_review(payload: dict) -> tuple[bool, dict]:
    """Independent, fail-closed review for high-confidence proposals."""
    if payload.get("layer") != "high" or not payload.get("excerpt") or len(set(payload.get("sources") or [])) < 3 or not payload.get("valid_from"):
        return False, {"deterministic": False, "reason": "deterministic checks failed"}
    model = os.environ.get("LLM_REVIEW_MODEL", "")
    extractor = os.environ.get("LLM_MODEL", "")
    if not model or model == extractor:
        return False, {"deterministic": True, "reason": "independent model unavailable"}
    try:
        from app.llm.client import complete_json
        prompt = "review-v1"
        result = complete_json([{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        ok = isinstance(result, dict) and result.get("approved") is True
        return ok, {"deterministic": True, "model": model, "prompt": prompt, "reason": result.get("reason", "") if isinstance(result, dict) else "invalid response"}
    except Exception:
        return False, {"deterministic": True, "model": model, "prompt": "review-v1", "reason": "review model failed"}


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


_VOTE_RANK = {"unmarked": 0, "bonus_explicit": 1, "required_explicit": 2}


def summarize_requirement_votes(votes: dict[str, str], companies: dict[str, str]) -> dict:
    """Collapse one vote per de-duplicated JD and decide the formal kind."""
    clean = {eid: vote for eid, vote in votes.items() if vote in _VOTE_RANK}
    counts = Counter(clean.values())
    classified = counts["required_explicit"] + counts["bonus_explicit"]
    source_sets = {
        kind: {normalize_company(companies.get(eid, "")) for eid, vote in clean.items() if vote == kind and companies.get(eid)}
        for kind in ("required_explicit", "bonus_explicit")
    }
    source_sets = {kind: {name for name in names if name and not is_channel_name(name)} for kind, names in source_sets.items()}
    proposed = None
    reason = "未达到 60% 明确性质或两个独立源"
    if classified:
        for kind, label in (("required_explicit", "required"), ("bonus_explicit", "bonus")):
            if counts[kind] / classified >= 0.60 and len(source_sets[kind]) >= 2:
                proposed = label
                reason = f"{counts[kind]}/{classified} 明确票，{len(source_sets[kind])} 个独立源"
                break
    return {
        "required_votes": counts["required_explicit"],
        "bonus_votes": counts["bonus_explicit"],
        "unmarked_votes": counts["unmarked"],
        "classified_vote_count": classified,
        "independent_source_count": len(source_sets.get("required_explicit", set()) | source_sets.get("bonus_explicit", set())),
        "vote_evidence": sorted(clean),
        "proposed_kind": proposed,
        "decision_reason": reason,
    }


def infer_requirement_group(excerpt: str, *, fallback: str = "") -> tuple[str, int]:
    text = excerpt or ""
    if not any(token in text for token in ("或", "任选", "至少", "任一")):
        return fallback, 1
    match = re.search(r"至少\s*(\d+)", text)
    minimum = int(match.group(1)) if match else 1
    return fallback or "group-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], max(1, minimum)


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
    if data.get("kind") == "skill_merge_proposal" and review in ("approved", "auto_passed"):
        graph.apply_skill_merge(data)
    if data.get("approved_kind") in ("required", "bonus"):
        data["kind_edge"] = data["approved_kind"]
    vote_blocked = data.get("kind") == "requires_add" and "proposed_kind" in data and not data.get("proposed_kind") and not data.get("approved_kind")
    if data.get("kind") != "extract_failed" and data.get("skill_id") and review in ("approved", "auto_passed") and not vote_blocked:
        graph.apply_requires(data)
    if data.get("definition_claims") and review in ("approved", "auto_passed"):
        graph.apply_definition_claims(data.get("job_id") or "", data["definition_claims"], event_id=event_id)
    graph.record_review_decision(event_id, review=review, payload=data, reason=str(data.get("review_reason") or ""))
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
            candidate_type = classify_skill_candidate(
                skill.name,
                action=skill.action,
                context=skill.context,
                candidate_type=skill.candidate_type,
            )
            if candidate_type == "generic":
                continue
            if candidate_type == "broad_domain" and section != "duty" and not (skill.action or skill.context):
                continue
            derived = brand_action_skill(skill.name, skill.action, skill.context)
            if candidate_type == "brand" and not derived:
                # Keep a market observation, but never let a naked brand become
                # a formal requirement. It is still useful in the evidence view.
                pending_names.append((snap, skill, section, True, candidate_type))
                continue
            if derived:
                skill = skill.model_copy(update={"name": derived, "raw_name": skill.raw_name or skill.name})
            pending_names.append((snap, skill, section, bool(candidate_type == "brand" and not derived), candidate_type))

    # 并列串拆到条目级：C/C++ → C、C++ 两条，下游按名聚类/对齐/计覆盖
    expanded: list[tuple] = []
    for snap, sk, section, watch_only, candidate_type in pending_names:
        for piece in split_composite(sk.name, index):
            expanded.append((snap, sk.model_copy(update={"name": piece}), section, watch_only, candidate_type))

    names = [sk.name for _, sk, _, _, _ in expanded]
    clustered = surface_clusters(names) if names else []
    centroid_for = {}
    for group in clustered:
        centroid = max(group, key=len)
        for name in group:
            centroid_for[name] = (centroid, group)

    members_by_centroid: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for snap, skill, _, _, _ in expanded:
        centroid, _ = centroid_for.get(skill.name, (skill.name, [skill.name]))
        members_by_centroid[centroid].append((skill.name, skill.category or ""))
    category_for = {
        centroid: _merge_category(members) for centroid, members in members_by_centroid.items()
    }

    merge_proposals: set[tuple[str, str, str]] = set()
    for snap, skill, section, watch_only, candidate_type in expanded:
        centroid, group = centroid_for.get(skill.name, (skill.name, [skill.name]))
        # Embeddings may suggest a merge, but cannot silently rewrite a skill ID.
        hit = align_skill(centroid, index, allow_embedding=False) or align_skill(skill.name, index, allow_embedding=False)
        semantic_hit, semantic_score = nearest_skill(centroid, index) if hit is None and index else (None, -1.0)
        if semantic_hit is not None and semantic_score >= 0.70 and semantic_hit["id"] != _stable_id("skill-", centroid):
            merge_proposals.add((semantic_hit["id"], centroid, _stable_id("skill-", centroid)))
        if hit is None:
            skill_id = _stable_id("skill-", centroid)
            hit = {
                "id": skill_id,
                "name": centroid,
                "synonyms": list(dict.fromkeys(group)),
                "embedding": embed([centroid])[0],
                "category": category_for.get(centroid, ""),
                "candidate_type": candidate_type,
                "watch_only": watch_only,
            }
            graph.upsert_skill(hit)
            index.append(hit)
        elif normalize_surface(skill.name) == normalize_surface(hit.get("name") or "") and skill.name not in (hit.get("synonyms") or []):
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
                "candidate_type": candidate_type,
                "watch_only": watch_only,
                "votes": {},
                "group_id": skill.group_id or infer_requirement_group(skill.excerpt)[0],
                "min_required": max(skill.min_required, infer_requirement_group(skill.excerpt)[1]),
            },
        )
        rec["evidence"].add(snap["id"])
        if skill.group_id:
            rec["group_id"] = skill.group_id
            rec["min_required"] = max(rec.get("min_required", 1), skill.min_required)
        previous_vote = rec["votes"].get(snap["id"], "unmarked")
        if _VOTE_RANK.get(skill.vote, 0) >= _VOTE_RANK.get(previous_vote, 0):
            rec["votes"][snap["id"]] = skill.vote
        rec["confidence"] = max(rec["confidence"], skill.confidence)
        if skill.excerpt:
            rec["excerpt"] = skill.excerpt

    watching = []
    pooled = []
    for skill_id, rec in mentions.items():
        rate = coverage(mentioned_in=len(rec["evidence"]), cluster_size=cluster_size)
        if rec.get("watch_only") or not pool_skill(section=rec["section"], coverage_rate=rate):
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
        vote_summary = summarize_requirement_votes(rec["votes"], company_by_evidence)
        proposed_kind = vote_summary["proposed_kind"]
        payload = {
            "kind": "requires_add",
            "job_id": job_id,
            "job_name": job_name,
            "domain": domain,
            "skill_id": skill_id,
            "skill_name": rec["skill"]["name"],
            "category": rec["category"],
            "kind_edge": proposed_kind or rec["kind"],
            **vote_summary,
            "proficiency": rec["proficiency"],
            "layer": layer,
            "confidence": rec["confidence"],
            "sources": sorted(rec["evidence"]),
            "excerpt": rec["excerpt"],
            "raw_name": rec["skill"].get("raw_name") or rec["skill"]["name"],
            "candidate_type": rec.get("candidate_type") or "unknown",
            "group_id": rec.get("group_id") or None,
            "min_required": int(rec.get("min_required") or 1),
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
        review_meta = {}
        if passthrough_enabled() and layer == "high" and proposed_kind:
            approved, review_meta = automatic_review(payload)
            if approved:
                review = "auto_passed"
                payload["automatic_review"] = review_meta
        event = {
            "id": _event_id(payload),
            "kind": "requires_add",
            "at": datetime.now(timezone.utc).isoformat(),
            "confidence": rec["confidence"],
            "review": review,
            "payload": payload,
            "model": review_meta.get("model", ""),
            "prompt": review_meta.get("prompt", ""),
        }
        graph.upsert_event(event, job_id=job_id)
        _emit("review_enqueued", event)
        if review == "auto_passed":
            graph.apply_requires(payload)
        events.append(event)
    for canonical_id, proposed_name, old_skill_id in sorted(merge_proposals):
        payload = {
            "kind": "skill_merge_proposal",
            "canonical_skill_id": canonical_id,
            "old_skill_id": old_skill_id,
            "proposed_name": proposed_name,
            "reason": "embedding_neighbour_only",
            "layer": "mid",
        }
        event = {
            "id": _event_id(payload),
            "kind": "skill_merge_proposal",
            "at": datetime.now(timezone.utc).isoformat(),
            "confidence": 0.0,
            "review": "pending",
            "payload": payload,
        }
        graph.upsert_event(event, job_id=None)
        _emit("review_enqueued", event)
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
