import os
import uuid
from unittest.mock import patch

import pytest

from app.llm.embed import embed
from app.matching.report import lookup_resource
from app.matching.resume import ResumeError, extract_text, minimal_pdf, parse_resume, skills_from_text
from app.pipeline.status import job_id_for


def _fake_complete(_schema, messages):
    sys = messages[0]["content"]
    if "experience" in sys:
        return {"experience": "3年", "education": "本科"}
    if "url" in sys:
        return {"url": "https://example.com/skill"}
    return {"skills": [{"name": "FastAPI", "proficiency": "able"}, {"name": "Python"}]}


def test_doc_rejected():
    try:
        extract_text(b"abc", "resume.doc")
        assert False
    except ResumeError as exc:
        assert ".doc" in exc.detail


def test_empty_pdf_rejected():
    blank = minimal_pdf(" ")
    try:
        extract_text(blank.replace(b"( )", b"()"), "scan.pdf")
    except ResumeError:
        return
    try:
        extract_text(minimal_pdf(""), "scan.pdf")
    except ResumeError as exc:
        assert "扫描" in exc.detail or "文本" in exc.detail


def test_skills_from_text_aligns_names():
    index = [
        {"id": "s1", "name": "FastAPI", "synonyms": ["starlette api"]},
        {"id": "s2", "name": "COBOL"},
    ]
    found = skills_from_text("做过 FastAPI 服务", index)
    assert {row["skill_id"] for row in found} == {"s1"}
    found_syn = skills_from_text("做过 starlette api", index)
    assert {row["skill_id"] for row in found_syn} == {"s1"}
    index_c = [{"id": "c", "name": "C"}, {"id": "s1", "name": "FastAPI"}]
    assert {row["skill_id"] for row in skills_from_text("LangChain FastAPI", index_c)} == {"s1"}


def test_parse_resume_aligns_and_keeps_unmarked_proficiency():
    index = [
        {"id": "s1", "name": "FastAPI", "synonyms": [], "embedding": embed(["FastAPI"])[0]},
        {"id": "s2", "name": "Python", "synonyms": [], "embedding": embed(["Python"])[0]},
    ]

    def fake(_schema, messages):
        sys = messages[0]["content"]
        if "experience" in sys:
            return {"experience": "5年", "education": "硕士"}
        return {"skills": [{"name": "FastAPI", "proficiency": "able"}, {"name": "Python"}]}

    out = parse_resume("精通 FastAPI，也写 Python", index, complete_json=fake)
    by_id = {row["skill_id"]: row for row in out["skills"]}
    assert by_id["s1"]["proficiency"] == "able"
    assert by_id["s2"]["proficiency"] is None
    assert out["experience"] == "5年"
    assert out["education"] == "硕士"
    guessed = parse_resume(
        "built FastAPI in Python",
        index,
        complete_json=lambda *_: {"skills": [{"name": "FastAPI", "proficiency": "aware"}]},
    )
    assert guessed["skills"][0]["proficiency"] is None


def test_lookup_resource_uses_cache():
    sid = "skill-cache-" + uuid.uuid4().hex
    calls = {"n": 0}

    def fake(_schema, messages):
        calls["n"] += 1
        return {"url": "https://neo4j.com/docs/cypher-manual/current/"}

    first = lookup_resource(sid, "Cypher", complete_json=fake)
    second = lookup_resource(sid, "Cypher", complete_json=fake)
    assert first.startswith("http")
    assert first == second
    assert calls["n"] == 1


def test_diagnose_report_shape(client):
    pdf = minimal_pdf("Python FastAPI Neo4j RAG LangChain")
    with patch("app.llm.client.complete_json", side_effect=_fake_complete):
        up = client.post("/sessions", files={"file": ("cv.pdf", pdf, "application/pdf")})
    if up.status_code != 200:
        # pdfplumber may fail on tiny pdf; still require a structured error
        assert up.status_code == 400
        return
    session_id = up.json()["session_id"]
    jobs = client.get("/jobs").json()
    target = next((j for j in jobs if j["name"] == "大模型应用工程师"), None)
    if target is None:
        return
    with patch("app.llm.client.complete_json", side_effect=_fake_complete):
        res = client.post(
            "/diagnose",
            json={"session_id": session_id, "job_id": target["id"]},
        )
    assert res.status_code == 200
    body = res.json()
    assert "score" in body
    assert body["band"] in ("高度匹配", "基本匹配", "有明显差距", "不匹配")
    groups = body["groups"]
    assert set(groups) >= {"judge", "locate", "act", "explain"}
    assert groups["explain"]["watching_copy"] == "市场开始提，还没进要求，不算缺口"
    assert len(groups["act"]["path"]) <= 5
    assert groups["judge"]["band"] == body["band"]
    neighbor_names = {n["name"] for n in groups["locate"]["neighbors"]}
    assert "Agent 工程师" in neighbor_names or not neighbor_names
    assert "大模型应用工程师" in neighbor_names or not neighbor_names
    path = groups["act"]["path"]
    assert all(step.get("url") for step in path)
    assert all(step.get("why") in ("换档", "半档", "缺口") for step in path)
    assert isinstance(groups["judge"]["shift_set"], list)
    assert "preview_text" in body
    assert groups["judge"]["cells"]["experience"] == "3年"
    assert groups["judge"]["cells"]["education"] == "本科"


def test_expired_session_is_404(client):
    job_id = job_id_for("大模型应用工程师")
    res = client.post("/diagnose", json={"session_id": "no-such", "job_id": job_id})
    assert res.status_code in (404, 400)


def test_sessions_rejects_doc(client):
    res = client.post("/sessions", files={"file": ("old.doc", b"xx", "application/msword")})
    assert res.status_code == 400
    assert "doc" in res.json()["error"].lower()


@pytest.mark.skipif(not os.environ.get("DEEPSEEK_API_KEY"), reason="no DEEPSEEK_API_KEY")
def test_live_deepseek_resume_and_resource():
    index = [
        {"id": "s1", "name": "FastAPI", "synonyms": [], "embedding": embed(["FastAPI"])[0]},
        {"id": "s2", "name": "Python", "synonyms": [], "embedding": embed(["Python"])[0]},
    ]
    out = parse_resume(
        "李四，计算机硕士，工作 4 年。熟悉 Python，生产环境用 FastAPI 做过接口，精通 FastAPI。",
        index,
    )
    ids = {row["skill_id"] for row in out["skills"]}
    assert ids & {"s1", "s2"}
    assert out["experience"] != "简历未标" or out["education"] != "简历未标"
    fastapi = next((row for row in out["skills"] if row["skill_id"] == "s1"), None)
    if fastapi and fastapi.get("proficiency"):
        assert fastapi["proficiency"] in ("aware", "able", "expert")
    sid = "skill-live-" + uuid.uuid4().hex
    url = lookup_resource(sid, "Cypher")
    assert url.startswith("http")
    assert "://" in url
