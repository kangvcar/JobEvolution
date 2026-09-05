import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from httpx2 import Request
from openai import APIError

from app import graph
from app.llm.embed import embed
from app.pipeline.align import align_skill
from app.pipeline.constants import COVERAGE_THRESHOLD, FAT_SLICE_CAP
from app.pipeline.extract import ExtractedJd, augment_extracted_skills, coerce_extracted, parse_extracted
from app.pipeline.__main__ import match_target, select_snapshots
from app.pipeline.gate import (
    apply_event,
    confidence_layer,
    coverage,
    pool_skill,
    run_extract_and_gate,
    summarize_requirement_votes,
)
from app.pipeline.sections import section_of, split_sections
from app.pipeline.status import job_id_for
from conftest import graph_clean


ADMIN = os.environ.get("ADMIN_PASSWORD", "change-me")


def test_confidence_layer_priority():
    assert confidence_layer(excerpt="", n_sources=9, extract_confidence=0.99) == "low"
    assert confidence_layer(excerpt="FastAPI", n_sources=3, extract_confidence=0.8) == "high"
    assert confidence_layer(excerpt="FastAPI", n_sources=2, extract_confidence=0.5) == "mid"
    assert confidence_layer(excerpt="FastAPI", n_sources=1, extract_confidence=0.4) == "low"


def test_requirement_vote_summary_uses_explicit_ratio_and_independent_sources():
    votes = {f"r{i}": "required_explicit" for i in range(16)}
    votes.update({f"b{i}": "bonus_explicit" for i in range(4)})
    votes.update({f"u{i}": "unmarked" for i in range(5)})
    companies = {key: ("甲" if key.startswith("r") and int(key[1:]) < 8 else "乙") for key in votes}
    summary = summarize_requirement_votes(votes, companies)
    assert summary["proposed_kind"] == "required"
    assert summary["required_votes"] == 16 and summary["bonus_votes"] == 4 and summary["unmarked_votes"] == 5

    low = summarize_requirement_votes(
        {"r": "required_explicit", **{f"u{i}": "unmarked" for i in range(8)}},
        {"r": "甲"},
    )
    assert low["proposed_kind"] is None


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


def test_extract_bad_payload_fails():
    calls = {"n": 0}

    def bad(_messages):
        calls["n"] += 1
        return {"nope": True}

    with pytest.raises(ValueError):
        parse_extracted(bad)
    assert calls["n"] == 1


def test_vocab_candidate_recall_keeps_source_trace():
    parsed = ExtractedJd.model_validate(
        {
            "job_name": "测试岗",
            "skills": [
                {
                    "name": "Python",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 Python",
                }
            ],
        }
    )
    augmented = augment_extracted_skills(
        parsed,
        "任职要求：熟悉 Python、FastAPI，具备 GPT 使用经验。",
        [
            {"id": "python", "name": "Python", "synonyms": []},
            {"id": "fastapi", "name": "FastAPI", "synonyms": []},
            {"id": "gpt", "name": "GPT", "synonyms": []},
        ],
        threshold=0.7,
    )
    assert [skill.name for skill in augmented.skills] == ["Python", "FastAPI"]
    assert augmented.skills[-1].excerpt == "FastAPI"


def test_match_target_prefers_longer_names():
    assert match_target("大模型应用工程师") == "大模型应用工程师"
    assert match_target("Agent工程师") == "Agent 工程师"
    assert match_target("高级算法工程师（图像）") == "算法工程师"


def _write_jd(jd, name, title, company, observed_at="2024-06-01"):
    (jd / name).write_text(
        json.dumps(
            {
                "title": title,
                "company": company,
                "body": "x",
                "id": name,
                "observed_at": observed_at,
            }
        ),
        encoding="utf-8",
    )


def test_select_contest_pair_takes_all_dedup_companies(tmp_path):
    jd = tmp_path / "jd"
    jd.mkdir()
    for i in range(5):
        _write_jd(jd, f"jd-a{i}.json", "Agent 工程师", f"公司{i}")
    _write_jd(jd, "jd-a-dup.json", "Agent工程师", "公司0")
    _write_jd(jd, "jd-llm.json", "大模型应用工程师", "公司甲")
    _write_jd(jd, "jd-llm-dup.json", "大模型应用工程师", "公司甲")
    picked = select_snapshots(jd)
    agent = [d for d in picked if "Agent" in (d.get("title") or "")]
    assert len(agent) == 5
    llm = [d for d in picked if d.get("title") == "大模型应用工程师"]
    assert len(llm) == 1


def test_select_fat_job_uses_two_time_slices(tmp_path):
    jd = tmp_path / "jd"
    jd.mkdir()
    for i in range(40):
        _write_jd(
            jd,
            f"jd-f{i:02d}.json",
            "算法工程师",
            f"公司{i}",
            observed_at=f"2024-{(i // 20) + 1:02d}-01",
        )
    picked = select_snapshots(jd)
    fat = [d for d in picked if d.get("title") == "算法工程师"]
    assert len(fat) == 2 * FAT_SLICE_CAP
    assert {d["observed_at"][:7] for d in fat} == {"2024-01", "2024-02"}


def test_select_other_targets_take_deduped_all(tmp_path):
    jd = tmp_path / "jd"
    jd.mkdir()
    for i in range(3):
        _write_jd(jd, f"jd-e{i}.json", "数据工程师", f"公司{i}")
    _write_jd(jd, "jd-e-dup.json", "数据工程师", "公司0")
    picked = select_snapshots(jd)
    assert len(picked) == 3


def test_select_alias_near_names_pass_pre_filter(tmp_path):
    jd = tmp_path / "jd"
    jd.mkdir()
    titles = [
        "大模型应用开发工程师",
        "大模型开发专家",
        "Agent平台研发",
        "智能体训练师",
        "Prompt工程师",
    ]
    for i, title in enumerate(titles):
        _write_jd(jd, f"jd-n{i}.json", title, f"公司{i}")
    _write_jd(jd, "jd-x.json", "会计", "公司x")
    picked = select_snapshots(jd)
    got = {d.get("title") for d in picked}
    assert got == set(titles)
    assert all(d.get("alias_candidate") for d in picked)


def test_extract_cache_hits_on_second_run(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
    calls = {"n": 0}

    def counting(_messages):
        calls["n"] += 1
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

    events1 = run_extract_and_gate(snaps, complete_json=counting, workers=1, cache=True)
    first_calls = calls["n"]
    assert first_calls == len(snaps)
    events2 = run_extract_and_gate(snaps, complete_json=counting, workers=1, cache=True)
    assert calls["n"] == first_calls
    adds1 = [e for e in events1 if e.get("kind") == "requires_add"]
    adds2 = [e for e in events2 if e.get("kind") == "requires_add"]
    assert adds1 and adds2
    assert [e["id"] for e in adds1] == [e["id"] for e in adds2]
    graph_clean(suffix)


def test_extract_retries_transient_failure_and_records_checkpoint(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9, companies=("甲",))
    calls = {"n": 0}
    stable = _extract_fn("熟悉 FastAPI", 0.9, "requirement")

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("temporary provider failure")
        return stable(messages)

    events = run_extract_and_gate(snapshots, complete_json=flaky, workers=1)
    assert calls["n"] == 3
    assert not [event for event in events if event.get("kind") == "extract_failed"]
    with graph._driver.session() as session:
        row = session.run(
            "MATCH (e:EvolutionEvent {kind: 'extract_completed'}) WHERE e.payload CONTAINS $id RETURN count(e) AS n",
            id=snapshots[0]["id"],
        ).single()
    assert row["n"] == 1
    graph_clean(suffix)


def test_gate_restores_evidence_for_fresh_graph(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
    graph.delete_evidence_many([snapshot["id"] for snapshot in snapshots])

    run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.9, "requirement"),
        workers=1,
    )

    evidence = graph.list_job_evidence(job_id_for("大模型应用工程师"))
    assert {row["id"] for row in evidence} >= {snapshot["id"] for snapshot in snapshots}
    graph_clean(suffix)


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
    def flash(_messages):
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

    parsed = parse_extracted(flash)
    assert parsed.skills[0].kind == "required"
    assert parsed.skills[0].section == "requirement"


def test_extract_requires_excerpt():
    def ok(_messages):
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

    parsed = parse_extracted(ok)
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
    snaps = _jd_snaps(tmp_path, suffix, excerpt="x", confidence=0.9)

    def bad(_messages):
        return {"nope": True}

    events = run_extract_and_gate(snaps[:1], complete_json=bad)
    assert events
    assert events[0]["kind"] == "extract_failed"
    assert events[0]["review"] == "pending"
    from app import graph

    graph_clean(suffix)


def test_queue_requires_admin_password(client):
    assert client.get("/admin/queue").status_code == 401
    ok = client.get("/admin/queue", headers={"X-Admin-Password": ADMIN})
    assert ok.status_code == 200
    assert isinstance(ok.json(), list)


def test_admin_password_hint_requires_demo_flag(client, monkeypatch):
    monkeypatch.delenv("NEXT_PUBLIC_SHOW_ADMIN_PASSWORD", raising=False)
    assert client.get("/admin/password-hint").status_code == 404
    monkeypatch.setenv("NEXT_PUBLIC_SHOW_ADMIN_PASSWORD", "1")
    response = client.get("/admin/password-hint")
    assert response.status_code == 200
    assert response.json()["password"] == ADMIN


def test_passthrough_default_off_and_low_never_auto(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
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
    low_snaps = _jd_snaps(tmp_path, suffix + "l", excerpt="", confidence=0.9)
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
    graph_clean(suffix)


def test_approve_writes_evidence_id_on_requires(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.9)
    events = run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.9, "requirement"),
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending
    event_id = pending[0]["id"]
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
    graph_clean(suffix)


def test_low_confirm_is_approved_not_auto_passed(tmp_path, client):
    from app import graph

    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(tmp_path, suffix, excerpt="熟悉 FastAPI", confidence=0.2)
    events = run_extract_and_gate(
        snapshots,
        complete_json=_extract_fn("熟悉 FastAPI", 0.2, "requirement"),
    )
    pending = [e for e in events if e.get("review") == "pending" and e.get("payload", {}).get("layer") == "low"]
    assert pending
    body = client.post(
        f"/admin/queue/{pending[0]['id']}/approve",
        headers={"X-Admin-Password": ADMIN},
        json={},
    ).json()
    assert body["review"] == "approved"
    assert body["review"] != "auto_passed"
    graph_clean(suffix)


def test_extract_target_and_category_coerce():
    def flash(_messages):
        return {
            "job_name": "大模型平台研发",
            "target": "大模型应用工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "LangChain 编排",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 LangChain",
                    "section": "requirement",
                    "category": "framework",
                },
                {
                    "name": "SQL",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.8,
                    "excerpt": "会写 SQL",
                    "section": "requirement",
                    "category": "语言",
                },
                {
                    "name": "摆摊",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.5,
                    "excerpt": "摆摊",
                    "section": "requirement",
                    "category": "烹饪",
                },
            ],
        }

    parsed = parse_extracted(flash)
    assert parsed.target == "大模型应用工程师"
    assert parsed.skills[0].category == "framework"
    assert parsed.skills[1].category == "language"
    assert parsed.skills[2].category == ""


def test_extract_invalid_target_becomes_empty():
    def flash(_messages):
        return {
            "job_name": "Agent 工程师",
            "target": "即时配送优化师",
            "domain": "ai",
            "skills": [],
        }

    parsed = parse_extracted(flash)
    assert parsed.target == ""


def test_extract_default_target_and_category_when_missing():
    def flash(_messages):
        return {
            "job_name": "Agent 工程师",
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

    parsed = parse_extracted(flash)
    assert parsed.target == ""
    assert parsed.skills[0].category == ""


def test_gate_prefers_target_over_embed_align(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(tmp_path, suffix, excerpt="熟悉 LangFrame", confidence=0.9, body="任职要求：熟悉 LangFrame。", companies=("甲", "乙"))

    def complete(_messages):
        return {
            "job_name": "即时配送调度研发",
            "target": "大模型应用工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "LangFrame",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 LangFrame",
                    "section": "requirement",
                }
            ],
        }

    events = run_extract_and_gate(snaps, complete_json=complete, workers=1)
    adds = [e for e in events if e.get("kind") == "requires_add"]
    assert adds
    assert all(e["payload"]["job_name"] == "大模型应用工程师" for e in adds)
    graph_clean(suffix)


def test_gate_invalid_target_falls_back_to_align(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(tmp_path, suffix, excerpt="熟悉 LangFrame", confidence=0.9, body="任职要求：熟悉 LangFrame。", companies=("甲", "乙"))

    def complete(_messages):
        return {
            "job_name": "Agent 工程师",
            "target": "即时配送优化师",
            "domain": "ai",
            "skills": [
                {
                    "name": "LangFrame",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 LangFrame",
                    "section": "requirement",
                }
            ],
        }

    events = run_extract_and_gate(snaps, complete_json=complete, workers=1)
    adds = [e for e in events if e.get("kind") == "requires_add"]
    assert adds
    assert all(e["payload"]["job_name"] == "Agent 工程师" for e in adds)
    graph_clean(suffix)


def test_gate_sends_alias_batch_to_cluster_before_target_alignment(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 LangFrame",
        confidence=0.9,
        body="任职要求：熟悉 LangFrame。",
        companies=("近名甲", "近名乙"),
    )
    for snapshot in snapshots:
        snapshot["alias_candidate"] = True

    def complete(_messages):
        return {
            "job_name": "AI 智能体开发",
            "target": "Agent 工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "LangFrame",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 LangFrame",
                    "section": "requirement",
                }
            ],
        }

    run_extract_and_gate(snapshots, complete_json=complete, workers=1)
    evidence = graph.list_job_evidence(job_id_for("Agent 工程师"))
    assert not {row["id"] for row in evidence} & {snapshot["id"] for snapshot in snapshots}
    graph_clean(suffix)


def test_gate_ignores_alias_cluster_when_classification_fails(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snapshots = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 LangFrame",
        confidence=0.9,
        body="任职要求：熟悉 LangFrame。",
    )
    for snapshot in snapshots:
        snapshot["alias_candidate"] = True
    classifications = {"n": 0}

    def complete(_messages):
        if "Classify" in _messages[0]["content"]:
            classifications["n"] += 1
            raise APIError(
                "classification unavailable",
                Request("POST", "https://example.test"),
                body=None,
            )
        return {
            "job_name": "AI 智能体开发",
            "target": "Agent 工程师",
            "domain": "ai",
            "skills": [],
        }

    assert run_extract_and_gate(snapshots, complete_json=complete, workers=1) == []
    assert classifications["n"] == 1
    graph_clean(suffix)


def test_gate_merges_large_alias_cluster_into_target(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    alias_name = f"AI 智能体开发{suffix}"
    snapshots = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 LangFrame",
        confidence=0.9,
        body="任职要求：熟悉 LangFrame。",
    )
    for snapshot in snapshots:
        snapshot["alias_candidate"] = True

    def complete(_messages):
        if "Classify" in _messages[0]["content"]:
            return {"kind": "alias", "alias_of": "Agent 工程师"}
        return {
            "job_name": alias_name,
            "target": "Agent 工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "LangFrame",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 LangFrame",
                    "section": "requirement",
                }
            ],
        }

    events = run_extract_and_gate(snapshots, complete_json=complete, workers=1)
    evidence = graph.list_job_evidence(job_id_for("Agent 工程师"))
    assert events
    assert {row["id"] for row in evidence} >= {snapshot["id"] for snapshot in snapshots}
    with graph._driver.session() as session:
        alias = session.run(
            "MATCH (:Job {id: $src})-[:ALIAS_OF]->(:Job {id: $dst}) RETURN count(*) AS n",
            src=job_id_for(alias_name),
            dst=job_id_for("Agent 工程师"),
        ).single()["n"]
        session.run("MATCH (j:Job {id: $id}) DETACH DELETE j", id=job_id_for(alias_name))
    assert alias == 1
    graph_clean(suffix)


def test_merge_category_majority_and_iron_veto():
    from app.pipeline.gate import _merge_category

    assert _merge_category([("Python", "domain"), ("numpy", "domain"), ("py", "domain")]) == "language"
    assert _merge_category([("a", "framework"), ("b", "framework"), ("c", "domain")]) == "framework"
    assert _merge_category([("a", ""), ("b", "framework")]) == "framework"
    assert _merge_category([("a", ""), ("b", "")]) == ""


def test_skill_ingest_writes_category_edge(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 LangFrame",
        confidence=0.9,
        body="任职要求：熟悉 LangFrame。",
    )
    events = run_extract_and_gate(
        snaps,
        complete_json=_extract_fn(
            "熟悉 LangFrame", 0.9, "requirement", category="framework", name="LangFrame"
        ),
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending
    assert pending[0]["payload"]["category"] == "framework"
    apply_event(pending[0]["id"], review="approved")
    job_id = pending[0]["payload"]["job_id"]
    with graph._driver.session() as session:
        row = session.run(
            """
            MATCH (:Job {id: $jid})-[:REQUIRES_VERSION {active: true}]->(v:RequirementVersion)
                  -[:FOR_SKILL]->(:Skill)-[:IN_CATEGORY]->(c:SkillCategory)
            WHERE v.valid_to IS NULL
            RETURN c.id AS cid, c.name AS cname
            """,
            jid=job_id,
        ).single()
    assert row is not None
    assert row["cid"] == "framework"
    assert row["cname"] == "框架"
    graph_clean(suffix)


def test_gate_iron_name_vetoes_category(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 Python",
        confidence=0.9,
        body="任职要求：熟悉 Python 与模型服务。",
    )
    events = run_extract_and_gate(
        snaps,
        complete_json=_extract_fn(
            "熟悉 Python", 0.9, "requirement", category="domain", name="Python"
        ),
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending
    assert pending[0]["payload"]["category"] == "language"
    apply_event(pending[0]["id"], review="approved")
    job_id = pending[0]["payload"]["job_id"]
    with graph._driver.session() as session:
        row = session.run(
            """
            MATCH (:Job {id: $jid})-[:REQUIRES_VERSION {active: true}]->(v:RequirementVersion)
                  -[:FOR_SKILL]->(:Skill)-[:IN_CATEGORY]->(c:SkillCategory)
            WHERE v.valid_to IS NULL
            RETURN c.id AS cid
            """,
            jid=job_id,
        ).single()
    assert row is not None and row["cid"] == "language"
    graph_clean(suffix)


def _approve_pending(events):
    for event in events:
        if event.get("review") == "pending":
            apply_event(event["id"], review="approved")


def test_expire_never_writes_valid_to_before_valid_from(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    old = _jd_snaps(
        tmp_path,
        suffix + "o",
        excerpt="熟悉 OldSkill",
        confidence=0.9,
        body="任职要求：熟悉 OldSkill。",
        at="2023-01-01",
    )
    _approve_pending(
        run_extract_and_gate(
            old,
            complete_json=_extract_fn("熟悉 OldSkill", 0.9, "requirement", name="OldSkill"),
            workers=1,
        )
    )
    new = _jd_snaps(
        tmp_path,
        suffix + "n",
        excerpt="熟悉 NewSkill",
        confidence=0.9,
        body="任职要求：熟悉 NewSkill。",
        companies=("丁", "戊", "己"),
        at="2024-06-01",
    )
    _approve_pending(
        run_extract_and_gate(
            new,
            complete_json=_extract_fn("熟悉 NewSkill", 0.9, "requirement", name="NewSkill"),
            workers=1,
        )
    )
    third = _jd_snaps(
        tmp_path,
        suffix + "t",
        excerpt="熟悉 ThirdSkill",
        confidence=0.9,
        body="任职要求：熟悉 ThirdSkill。",
        companies=("庚", "辛", "壬"),
        at="2024-01-01",
    )
    run_extract_and_gate(
        third,
        complete_json=_extract_fn("熟悉 ThirdSkill", 0.9, "requirement", name="ThirdSkill"),
        workers=1,
    )
    job_id = job_id_for("大模型应用工程师")
    with graph._driver.session() as session:
        rows = session.run(
            """
            MATCH (:Job {id: $jid})-[:REQUIRES_VERSION]->(v:RequirementVersion)-[:FOR_SKILL]->(s:Skill)
            WHERE s.name IN ['OldSkill', 'NewSkill']
            RETURN s.name AS name, v.valid_from AS vf, v.valid_to AS vt
            """,
            jid=job_id,
        ).data()
    by_name = {row["name"]: row for row in rows}
    assert by_name["OldSkill"]["vt"] is not None
    assert by_name["OldSkill"]["vt"] >= by_name["OldSkill"]["vf"]
    assert by_name["NewSkill"]["vt"] is None
    graph_clean(suffix)


def test_empty_keep_leaves_active_requires_untouched(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    seeded = _jd_snaps(
        tmp_path,
        suffix + "a",
        excerpt="熟悉 StableSkill",
        confidence=0.9,
        body="任职要求：熟悉 StableSkill。",
        at="2023-06-01",
    )
    _approve_pending(
        run_extract_and_gate(
            seeded,
            complete_json=_extract_fn("熟悉 StableSkill", 0.9, "requirement", name="StableSkill"),
            workers=1,
        )
    )

    def sparse(_messages):
        text = str(messages)
        if "StableSkill" not in text:
            return {"job_name": "大模型应用工程师", "domain": "ai", "skills": []}
        return {
            "job_name": "大模型应用工程师",
            "domain": "ai",
            "skills": [
                {
                    "name": "StableSkill",
                    "kind": "required",
                    "proficiency": "able",
                    "confidence": 0.9,
                    "excerpt": "熟悉 StableSkill",
                    "section": "requirement",
                }
            ],
        }

    mentioned = _jd_snaps(
        tmp_path,
        suffix + "b",
        excerpt="熟悉 StableSkill",
        confidence=0.9,
        body="任职要求：熟悉 StableSkill。",
        companies=("子",),
        at="2024-02-01",
    )
    silent = _jd_snaps(
        tmp_path,
        suffix + "c",
        excerpt="熟悉 StableSkill",
        confidence=0.9,
        body="任职要求：踏实肯干。",
        companies=("丑", "寅", "卯"),
        at="2024-02-01",
    )
    run_extract_and_gate(mentioned + silent, complete_json=sparse, workers=1)
    job_id = job_id_for("大模型应用工程师")
    with graph._driver.session() as session:
        row = session.run(
            """
            MATCH (:Job {id: $jid})-[rv:REQUIRES_VERSION {active: true}]->(v:RequirementVersion)
                  -[:FOR_SKILL]->(:Skill {name: 'StableSkill'})
            WHERE v.valid_to IS NULL
            RETURN count(rv) AS n
            """,
            jid=job_id,
        ).single()
    assert row["n"] == 1
    graph_clean(suffix)


def test_init_graph_writes_five_skill_categories():
    graph.init_graph()
    with graph._driver.session() as session:
        rows = session.run(
            "MATCH (c:SkillCategory) RETURN c.id AS id, c.name AS name ORDER BY c.id"
        ).data()
    assert {row["id"] for row in rows} == {"language", "framework", "platform", "engineering", "domain"}
    assert {row["name"] for row in rows} == {"语言", "框架", "平台", "工程", "领域知识"}


def _extract_fn(excerpt, confidence, section, category=None, name="FastAPI"):
    def complete(_messages):
        skill = {
            "name": name,
            "kind": "required",
            "proficiency": "able",
            "confidence": confidence,
            "excerpt": excerpt,
            "section": section,
        }
        if category is not None:
            skill["category"] = category
        return {
            "job_name": "大模型应用工程师",
            "domain": "ai",
            "skills": [skill],
        }

    return complete


def _jd_snaps(
    tmp_path,
    suffix,
    *,
    excerpt,
    confidence,
    body="任职要求：熟悉 FastAPI 与模型服务。",
    companies=("甲", "乙", "丙"),
    at=None,
):
    del excerpt, confidence
    from app import graph

    graph.init_graph()
    snaps = []
    for i, company in enumerate(companies):
        sid = f"jd-test-{suffix}-{i}"
        path = tmp_path / f"{sid}.json"
        doc = {
            "id": sid,
            "path": str(path),
            "source": "ats",
            "company": company,
            "title": "大模型应用工程师",
            "body": body,
            "city": "北京",
            "observed_at": at or f"2024-0{i+1}-01",
            "domain": "ai",
            "fingerprint": sid,
            "simhash": "0" * 16,
        }
        path.write_text("{}", encoding="utf-8")
        graph.upsert_evidence_many(
            [
                {
                    "id": sid,
                    "path": doc["path"],
                    "source": "ats",
                    "company": company,
                    "observed_at": doc["observed_at"],
                    "simhash": doc["simhash"],
                }
            ]
        )
        snaps.append(doc)
    return snaps


def test_unresolved_vote_blocks_passthrough_but_not_manual_approval(tmp_path):
    """判定票未形成性质：自动直通不落边；管理员手工批准按 kind_edge 落边。"""
    suffix = uuid.uuid4().hex[:8]
    snaps = _jd_snaps(
        tmp_path,
        suffix,
        excerpt="熟悉 VoteSkill",
        confidence=0.9,
        body="任职要求：熟悉 VoteSkill。",
    )
    events = run_extract_and_gate(
        snaps,
        complete_json=_extract_fn("熟悉 VoteSkill", 0.9, "requirement", name="VoteSkill"),
        workers=1,
    )
    pending = [e for e in events if e.get("review") == "pending"]
    assert pending and pending[0]["payload"]["proposed_kind"] is None
    job_id = pending[0]["payload"]["job_id"]

    def active_kinds():
        with graph._driver.session() as session:
            return session.run(
                """
                MATCH (:Job {id: $jid})-[:REQUIRES_VERSION {active: true}]->(v:RequirementVersion)
                      -[:FOR_SKILL]->(:Skill {name: 'VoteSkill'})
                RETURN collect(v.kind) AS kinds
                """,
                jid=job_id,
            ).single()["kinds"]

    apply_event(pending[0]["id"], review="auto_passed")
    assert active_kinds() == []
    apply_event(pending[0]["id"], review="approved")
    assert active_kinds() == ["required"]
    graph_clean(suffix)
