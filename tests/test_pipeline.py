import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.llm.embed import embed
from app.pipeline.align import align_skill
from app.pipeline.constants import COVERAGE_THRESHOLD
from app.pipeline.extract import ExtractedJd, coerce_extracted, parse_extracted
from app.pipeline.__main__ import match_target, select_snapshots
from app.pipeline.gate import (
    confidence_layer,
    coverage,
    pool_skill,
    run_extract_and_gate,
)
from app.pipeline.sections import section_of, split_sections


ADMIN = os.environ.get("ADMIN_PASSWORD", "change-me")


def _client():
    from app.main import app

    return TestClient(app)


def test_confidence_layer_priority():
    assert confidence_layer(excerpt="", n_sources=9, extract_confidence=0.99) == "low"
    assert confidence_layer(excerpt="FastAPI", n_sources=3, extract_confidence=0.8) == "high"
    assert confidence_layer(excerpt="FastAPI", n_sources=2, extract_confidence=0.5) == "mid"
    assert confidence_layer(excerpt="FastAPI", n_sources=1, extract_confidence=0.4) == "low"


def test_align_skill_synonym_beats_embed():
    index = [
        {
            "id": "skill-a",
            "name": "FastAPI",
            "synonyms": ["fast api"],
            "embedding": embed(["zzzz-unrelated"])[0],
        }
    ]
    hit = align_skill("fast api", index, embed_fn=embed)
    assert hit is not None and hit["id"] == "skill-a"


def test_align_skill_cosine_when_no_synonym():
    fastapi = embed(["fastapi"])[0]
    other = embed(["neo4j cypher"])[0]
    index = [
        {"id": "skill-a", "name": "FastAPI", "synonyms": [], "embedding": fastapi},
        {"id": "skill-b", "name": "Cypher", "synonyms": [], "embedding": other},
    ]
    hit = align_skill("FastAPI", index, embed_fn=embed)
    assert hit is not None and hit["id"] == "skill-a"
    miss = align_skill("totally-unknown-widget-xyz", index, embed_fn=embed)
    assert miss is None


def test_extract_retries_then_fails():
    calls = {"n": 0}

    def bad(_schema, _messages):
        calls["n"] += 1
        return {"nope": True}

    with pytest.raises(ValueError):
        parse_extracted(bad, retry=True)
    assert calls["n"] == 2


def test_match_target_prefers_longer_names():
    assert match_target("大模型应用工程师") == "大模型应用工程师"
    assert match_target("Agent工程师") == "Agent 工程师"
    assert match_target("高级算法工程师（图像）") == "算法工程师"


def test_select_snapshots_caps_per_job_and_company(tmp_path):
    jd = tmp_path / "jd"
    jd.mkdir()
    rows = [
        ("jd-1.json", "Agent 工程师", "甲"),
        ("jd-2.json", "Agent工程师", "乙"),
        ("jd-3.json", "Agent 工程师", "甲"),
        ("jd-4.json", "大模型应用工程师", "丙"),
    ]
    for name, title, company in rows:
        (jd / name).write_text(
            json.dumps({"title": title, "company": company, "body": "x", "id": name}),
            encoding="utf-8",
        )
    picked = select_snapshots(jd, per_job=8)
    agent = [d for d in picked if "Agent" in (d.get("title") or "")]
    assert len(agent) == 2
    assert {d["company"] for d in agent} == {"甲", "乙"}


def test_coerce_maps_model_aliases():
    coerced = coerce_extracted(
        {
            "job_name": "大语言模型算法工程师",
            "domain": "人工智能",
            "skills": [
                {
                    "name": "Python",
                    "kind": "technical",
                    "proficiency": "advanced",
                    "confidence": 95,
                    "excerpt": "优秀的Python编程能力",
                    "section": "responsibilities",
                },
                {
                    "name": "SQL",
                    "kind": "加分",
                    "proficiency": "熟练",
                    "confidence": 0.7,
                    "excerpt": "熟悉 SQL",
                    "section": "requirements",
                },
            ],
        }
    )
    parsed = ExtractedJd.model_validate(coerced)
    assert parsed.domain == "ai"
    assert parsed.skills[0].kind == "required"
    assert parsed.skills[0].proficiency == "expert"
    assert parsed.skills[0].section == "duty"
    assert parsed.skills[0].confidence == 0.95
    assert parsed.skills[1].kind == "bonus"
    assert parsed.skills[1].proficiency == "able"
    assert parsed.skills[1].section == "requirement"


def test_parse_extracted_accepts_flash_aliases():
    def flash(_schema, _messages):
        return {
            "job_name": "语音算法工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "语音识别",
                    "kind": "technical",
                    "proficiency": "advanced",
                    "confidence": 0.9,
                    "excerpt": "语音识别",
                    "section": "requirements",
                }
            ],
        }

    parsed = parse_extracted(flash, retry=False)
    assert parsed.skills[0].kind == "required"
    assert parsed.skills[0].section == "requirement"


def test_extract_requires_excerpt():
    def ok(_schema, _messages):
        return {
            "job_name": "大模型应用工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "FastAPI",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 FastAPI",
                    "section": "requirement",
                }
            ],
        }

    parsed = parse_extracted(ok, retry=True)
    assert isinstance(parsed, ExtractedJd)
    assert parsed.skills[0].excerpt


def test_benefits_not_pooled():
    body = "职责：开发接口。任职要求：会 Python。福利：有下午茶。公司介绍：我们是大厂。"
    parts = split_sections(body)
    assert "下午茶" in parts["benefit"]
    assert section_of(body, "下午茶") == "benefit"
    assert pool_skill(section="benefit", coverage_rate=1.0) is False
    assert pool_skill(section="requirement", coverage_rate=COVERAGE_THRESHOLD) is True
    assert pool_skill(section="duty", coverage_rate=COVERAGE_THRESHOLD - 0.01) is False


def test_coverage_is_mentions_over_cluster_size():
    assert coverage(mentioned_in=1, cluster_size=4) == 0.25
    assert coverage(mentioned_in=3, cluster_size=10) == 0.3


def test_extract_failure_enqueues_pending(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _three_source_snaps(tmp_path, suffix, excerpt="x", confidence=0.9)

    def bad(_schema, _messages):
        return {"nope": True}

    events = run_extract_and_gate(snaps[:1], complete_json=bad)
    assert events
    assert events[0]["kind"] == "extract_failed"
    assert events[0]["review"] == "pending"
    from app import graph

    _cleanup(graph, suffix)


def test_queue_requires_admin_password():
    client = _client()
    assert client.get("/admin/queue").status_code == 401
    ok = client.get("/admin/queue", headers={"X-Admin-Password": ADMIN})
    assert ok.status_code == 200
    assert isinstance(ok.json(), list)


def test_passthrough_default_off_and_low_never_auto(tmp_path):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _three_source_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
    client = _client()
    client.put(
        "/admin/passthrough",
        headers={"X-Admin-Password": ADMIN},
        json={"enabled": False},
    )
    events = run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.9, "requirement"),
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending
    low_snaps = _three_source_snaps(tmp_path, suffix + "l", excerpt="", confidence=0.9)
    client.put(
        "/admin/passthrough",
        headers={"X-Admin-Password": ADMIN},
        json={"enabled": True},
    )
    low_events = run_extract_and_gate(
        low_snaps,
        complete_json=_extract_fn("", 0.9, "requirement"),
    )
    assert all(e.get("review") != "auto_passed" for e in low_events)
    client.put(
        "/admin/passthrough",
        headers={"X-Admin-Password": ADMIN},
        json={"enabled": False},
    )
    _cleanup(graph, suffix)


def test_approve_writes_evidence_id_on_requires(tmp_path):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _three_source_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
    events = run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.9, "requirement"),
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending
    event_id = pending[0]["id"]
    client = _client()
    denied = client.post(f"/admin/queue/{event_id}/approve")
    assert denied.status_code == 401
    approved = client.post(
        f"/admin/queue/{event_id}/approve",
        headers={"X-Admin-Password": ADMIN},
        json={},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body.get("review") == "approved"
    job_id = pending[0]["payload"]["job_id"]
    slice_ = client.get(f"/graph/jobs/{job_id}").json()
    sources = []
    for edge in slice_["requires"]:
        sources.extend(edge.get("sources") or [])
    assert any(s.startswith("ev-") or s.startswith("jd-") or suffix in s for s in sources) or sources
    evidence_ids = {row["id"] for row in snapshots}
    assert evidence_ids & set(sources)
    _cleanup(graph, suffix)


def test_low_confirm_is_approved_not_auto_passed(tmp_path):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _three_source_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.2)
    events = run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.2, "requirement"),
    )
    pending = [e for e in events if e.get("review") == "pending" and e.get("payload", {}).get("layer") == "low"]
    assert pending
    client = _client()
    body = client.post(
        f"/admin/queue/{pending[0]['id']}/approve",
        headers={"X-Admin-Password": ADMIN},
        json={},
    ).json()
    assert body["review"] == "approved"
    assert body["review"] != "auto_passed"
    _cleanup(graph, suffix)


def _extract_fn(excerpt, confidence, section):
    def complete(_schema, _messages):
        return {
            "job_name": "大模型应用工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "FastAPI",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": confidence,
                    "excerpt": excerpt,
                    "section": section,
                }
            ],
        }

    return complete


def _three_source_snaps(tmp_path, suffix, *, excerpt, confidence):
    del excerpt, confidence
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    snaps = []
    for i, company in enumerate(("甲", "乙", "丙")):
        sid = f"jd-test-{suffix}-{i}"
        path = tmp_path / f"{sid}.json"
        body = "任职要求：熟悉 FastAPI 与模型服务。"
        doc = {
            "id": sid,
            "path": str(path),
            "source": "local",
            "company": company,
            "title": "大模型应用工程师",
            "body": body,
            "city": "北京",
            "observed_at": f"2024-0{i+1}-01",
            "domain": "ai",
            "fingerprint": sid,
            "simhash": "0" * 16,
        }
        path.write_text("{}", encoding="utf-8")
        graph.upsert_evidence(
            id=sid,
            path=doc["path"],
            source="local",
            company=company,
            observed_at=doc["observed_at"],
            simhash=doc["simhash"],
        )
        snaps.append(doc)
    return snaps


def _cleanup(graph, suffix):
    if graph._driver is None:
        return
    with graph._driver.session() as session:
        session.run(
            "MATCH (e:Evidence) WHERE e.id CONTAINS $s DETACH DELETE e",
            s=suffix,
        )
        session.run(
            "MATCH (ev:EvolutionEvent) WHERE ev.payload CONTAINS $s DETACH DELETE ev",
            s=suffix,
        )
