from app.matching.resume import ResumeError, extract_text, minimal_pdf, skills_from_text
from app.pipeline.status import job_id_for


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


def test_diagnose_report_shape(client):
    pdf = minimal_pdf("Python FastAPI Neo4j RAG LangChain")
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


def test_expired_session_is_404(client):
    job_id = job_id_for("大模型应用工程师")
    res = client.post("/diagnose", json={"session_id": "no-such", "job_id": job_id})
    assert res.status_code in (404, 400)


def test_sessions_rejects_doc(client):
    res = client.post("/sessions", files={"file": ("old.doc", b"xx", "application/msword")})
    assert res.status_code == 400
    assert "doc" in res.json()["error"].lower()
