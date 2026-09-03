import hmac
import os
import secrets
import subprocess
import sys
import time
import uuid
import logging
import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response, StreamingResponse

from app import graph
from app.matching.report import direction_report, evidence_map, market_signal_radar, migration_map, neighbor_name, recommend_jobs, simulate_job, wrap_report
from app.matching.resume import ResumeError, date_conflicts, evidence_level, extract_text, parse_resume
from app.matching.session import TTL as SESSION_TTL
from app.matching.session import load as load_session
from app.matching.session import save as save_session, update as update_session
from app.pipeline.gate import apply_event, passthrough_enabled, set_passthrough
from app.pipeline.status import job_id_for

_parse_attempts: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    graph.init_graph()
    yield
    graph.close_graph()


app = FastAPI(lifespan=lifespan)
_request_log = logging.getLogger("jobevolution.request")
_diagnose_attempts: dict[str, list[float]] = {}


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = await call_next(request)
    _request_log.info("request", extra={"request_id": request_id, "route": request.url.path, "status": response.status_code, "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
    response.headers["X-Request-ID"] = request_id
    return response
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse(
        {"error": str(exc.detail), "detail": None},
        status_code=exc.status_code,
    )


@app.get("/meta")
def meta():
    from app.ops_status import read as read_ops, stale as ops_stale
    return {
        "domains": graph.list_domains(),
        "graph_release": graph.public_release(),
        "model_provider": os.environ.get("LLM_PROVIDER", "configured model service"),
        "resume_retention_seconds": 3600,
        "resume_payload": "extracted text only",
        "ops": read_ops(),
        "stale": ops_stale(),
    }


@app.get("/v1/meta")
def v1_meta():
    return meta()


@app.get("/jobs")
def jobs(
    domain: str | None = None,
    status: str | None = None,
    q: str | None = Query(None),
    category: str | None = Query(None),
    level: str | None = Query(None, pattern="^(junior|mid|senior)$"),
):
    return graph.list_jobs(domain=domain, status=status, q=q, category=category, level=level)


@app.get("/v1/jobs")
def v1_jobs(domain: str | None = None, status: str | None = None, q: str | None = Query(None), category: str | None = Query(None), level: str | None = Query(None, pattern="^(junior|mid|senior)$")):
    return jobs(domain=domain, status=status, q=q, category=category, level=level)


@app.get("/jobs/{job_id}")
def job_detail(job_id: str):
    row = graph.get_public_job(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    row["events"] = graph.list_job_events(job_id)
    evidence = graph.list_job_evidence(job_id)
    row["sources"] = sorted({item["company"] for item in evidence if item.get("company")})
    row["definition"] = graph.current_definition(job_id)
    return row


@app.get("/v1/jobs/{job_id}")
def v1_job_detail(job_id: str):
    return job_detail(job_id)


@app.get("/graph/jobs/{job_id}")
def job_slice(job_id: str):
    row = graph.get_public_job(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    requires = graph.list_requires(job_id)
    skills = [
        {
            "id": edge["skill_id"],
            "name": edge["name"],
            "category_id": edge.get("category_id"),
            "category": edge.get("category"),
        }
        for edge in requires
    ]
    categories = {}
    for edge in requires:
        category_id = edge.get("category_id")
        category_name = edge.get("category")
        if category_id and category_name:
            categories[category_id] = {"id": category_id, "name": category_name}
    return {
        "job": row,
        "categories": list(categories.values()),
        "skills": skills,
        "requires": requires,
        "evidence": graph.list_job_evidence(job_id),
        "period_delta": graph.period_delta(job_id),
    }


@app.get("/v1/graph/jobs/{job_id}")
def v1_job_slice(job_id: str):
    return job_slice(job_id)


class DiagnoseBody(BaseModel):
    job_id: str | None = None
    job_ids: list[str] = []
    session_id: str | None = None


class RecommendBody(BaseModel):
    session_id: str


class SimulateBody(BaseModel):
    session_id: str
    job_ids: list[str] = []
    job_id: str | None = None
    assumed_skill_ids: list[str] = []
    watching_skill_ids: list[str] = []


@app.post("/sessions")
async def create_session(request: Request, file: UploadFile = File(...), consent: bool = Form(False)):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [stamp for stamp in _parse_attempts.get(ip, []) if stamp > now - 3600]
    if len(recent) >= 10:
        raise HTTPException(429, "解析次数已达每小时上限")
    _parse_attempts[ip] = recent + [now]
    if file.content_type not in {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
        raise HTTPException(400, "仅支持带文本层的 PDF 或 docx")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 10 MB")
    name = (file.filename or "").lower()
    if (name.endswith(".pdf") and data[:4] != b"%PDF") or (name.endswith(".docx") and data[:2] != b"PK"):
        raise HTTPException(400, "文件扩展名、MIME 与签名不一致")
    if not consent:
        raise HTTPException(400, "请先确认外部模型处理说明")
    try:
        text = extract_text(data, file.filename or "")
    except ResumeError as exc:
        raise HTTPException(400, exc.detail) from exc
    try:
        parsed = parse_resume(text, graph.list_skills())
    except Exception as exc:
        # 外部模型余额、限流或短暂故障不应变成无说明的 500。
        _request_log.warning("resume_parse_failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(503, "简历解析服务暂时不可用，请稍后重试") from exc
    session_id = save_session(
        {
            "preview_text": text[:4000],
            "profile": parsed.get("profile") or {},
            "education_items": parsed.get("education_items") or [],
            "experiences": parsed.get("experiences") or [],
            "projects": parsed.get("projects") or [],
            "skills": parsed["skills"],
            "evidence_fragments": parsed.get("evidence_fragments") or [],
            "date_conflicts": parsed.get("date_conflicts") or [],
            "user_added": [],
            "experience": parsed["experience"],
            "education": parsed["education"],
            "filename": file.filename,
            "graph_release": graph.public_release().get("id"),
            "expires_at": time.time() + SESSION_TTL,
        }
    )
    return {
        "session_id": session_id,
        "skills": parsed["skills"],
        "preview_text": text[:2000],
        "experience": parsed["experience"],
        "education": parsed["education"],
        "profile": parsed.get("profile") or {},
        "education_items": parsed.get("education_items") or [],
        "experiences": parsed.get("experiences") or [],
        "projects": parsed.get("projects") or [],
        "evidence_fragments": parsed.get("evidence_fragments") or [],
        "date_conflicts": parsed.get("date_conflicts") or [],
        "user_added": [],
        "expires_at": time.time() + SESSION_TTL,
        "graph_release": graph.public_release().get("id"),
    }


@app.post("/v1/sessions")
async def v1_create_session(request: Request, file: UploadFile = File(...), consent: bool = Form(False)):
    return await create_session(request=request, file=file, consent=consent)


class SessionUpdateBody(BaseModel):
    skills: list[dict] = []
    profile: dict = {}
    education_items: list[dict] = []
    experiences: list[dict] = []
    projects: list[dict] = []
    evidence_fragments: list[dict] = []
    user_added: list[dict] = []


@app.patch("/sessions/{session_id}")
def update_resume_session(session_id: str, body: SessionUpdateBody):
    session = load_session(session_id)
    if session is None:
        raise HTTPException(404, "session expired")
    cleaned = []
    for skill in body.skills:
        if not isinstance(skill, dict) or not skill.get("skill_id"):
            continue
        proficiency = skill.get("proficiency")
        if proficiency not in (None, "aware", "able", "expert"):
            proficiency = None
        cleaned.append({"skill_id": str(skill["skill_id"]), "name": str(skill.get("name") or skill["skill_id"]), "proficiency": proficiency})
    original_ids = {str(skill.get("skill_id")) for skill in session.get("skills") or [] if skill.get("skill_id")}
    fragments = []
    for fragment in body.evidence_fragments:
        if not isinstance(fragment, dict):
            continue
        sid = str(fragment.get("skill_id") or "")
        text = str(fragment.get("text") or "").strip()
        level = str(fragment.get("evidence_level") or "mention")
        if sid not in original_ids or not text or text not in (session.get("preview_text") or ""):
            raise HTTPException(400, "证据片段必须来自当前简历原文")
        if level not in ("mention", "use", "result"):
            raise HTTPException(400, "证据级无效")
        inferred = evidence_level(text, str(fragment.get("name") or sid))
        order = {"mention": 0, "use": 1, "result": 2}
        if order[level] > order[inferred]:
            raise HTTPException(400, "证据级不能超过简历原文支持的范围")
        fragment_id = str(fragment.get("id") or "resume-evidence-" + hashlib.sha256(f"{sid}:{text}".encode()).hexdigest()[:16])
        fragments.append({"id": fragment_id, "skill_id": sid, "text": text, "section": str(fragment.get("section") or "experience"), "evidence_level": level})
    added = []
    for item in body.user_added:
        if isinstance(item, dict) and item.get("skill_id") and str(item["skill_id"]) not in original_ids:
            added.append({"skill_id": str(item["skill_id"]), "name": str(item.get("name") or item["skill_id"]), "reason": "你补充的，简历尚未证明"})
    session["skills"] = cleaned
    session["profile"] = body.profile
    session["education_items"] = body.education_items
    session["experiences"] = body.experiences
    session["projects"] = body.projects
    session["evidence_fragments"] = fragments or session.get("evidence_fragments") or []
    session["user_added"] = added
    session["date_conflicts"] = date_conflicts(session.get("preview_text") or "")
    if not update_session(session_id, session):
        raise HTTPException(404, "session expired")
    return {
        "session_id": session_id,
        "skills": cleaned,
        "profile": session.get("profile") or {},
        "education_items": session.get("education_items") or [],
        "experiences": session.get("experiences") or [],
        "projects": session.get("projects") or [],
        "evidence_fragments": session.get("evidence_fragments") or [],
        "user_added": session.get("user_added") or [],
        "date_conflicts": session.get("date_conflicts") or [],
        "expires_at": session.get("expires_at"),
        "graph_release": session.get("graph_release"),
    }


@app.post("/diagnose")
def diagnose(body: DiagnoseBody, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [stamp for stamp in _diagnose_attempts.get(ip, []) if stamp > now - 60]
    if len(recent) >= 30:
        raise HTTPException(429, "诊断请求过于频繁，请稍后重试")
    _diagnose_attempts[ip] = recent + [now]
    selected_ids = [job_id for job_id in body.job_ids if job_id]
    if body.job_id and not selected_ids:
        selected_ids = [body.job_id]
    if not selected_ids:
        raise HTTPException(400, "请选择至少一个岗位")
    if len(selected_ids) > 2:
        raise HTTPException(400, "最多对照两个岗位")
    job = graph.get_any_job(selected_ids[0])
    if job is None:
        raise HTTPException(404, "not found")
    if job.get("status") == "candidate":
        raise HTTPException(400, "candidate")
    resume = load_session(body.session_id or "")
    if resume is None:
        raise HTTPException(404, "session expired")
    release_check = graph.diagnostic_release(selected_ids[0])
    if not release_check["ok"]:
        raise HTTPException(409, "岗位数据正在校验，暂不可诊断")
    resume["session_id"] = body.session_id
    if len(selected_ids) == 2:
        second = graph.get_any_job(selected_ids[1])
        if second is None or second.get("status") == "candidate" or not graph.diagnostic_release(selected_ids[1])["ok"]:
            raise HTTPException(409, "第二个岗位正在校验，暂不可诊断")
        report = direction_report(
            [{"id": selected_ids[0], "name": job.get("name"), "requires": graph.list_requires(selected_ids[0])}, {"id": selected_ids[1], "name": second.get("name"), "requires": graph.list_requires(selected_ids[1])}],
            resume,
        )
        report.update({"session_id": body.session_id, "graph_release": resume.get("graph_release")})
        return report
    requires = graph.list_requires(selected_ids[0])
    neighbor = None
    other = neighbor_name(job.get("name") or "")
    if other:
        oid = job_id_for(other)
        row = graph.get_public_job(oid)
        if row:
            neighbor = {"job": row, "requires": graph.list_requires(oid)}
    index = {row["id"]: row for row in graph.list_skills(with_embed=False)}
    watching = []
    for sid in job.get("watching") or []:
        skill = index.get(sid) or {}
        watching.append({"skill_id": sid, "name": skill.get("name") or sid})
    categories = {}
    for edge in requires:
        if edge.get("category_id") and edge.get("category"):
            categories[edge["category_id"]] = {
                "id": edge["category_id"],
                "name": edge["category"],
            }
    report = wrap_report(
        job=job,
        requires=requires,
        resume=resume,
        neighbor=neighbor,
        watching=watching,
        slice_data={
            "categories": list(categories.values()),
            "requires": requires,
            "period_delta": graph.period_delta(selected_ids[0]),
        },
    )
    report["metadata"]["graph_release"] = resume.get("graph_release") or graph.public_release().get("id")
    report["metadata"]["last_updated"] = graph.public_release().get("published_at")
    return report


@app.post("/diagnose/recommend")
def diagnose_recommend(body: RecommendBody):
    resume = load_session(body.session_id)
    if resume is None:
        raise HTTPException(404, "session expired")
    candidates = []
    for job in graph.list_jobs(domain=None, status=None, q=None):
        check = graph.diagnostic_release(job["id"])
        if not check["ok"]:
            continue
        candidates.append({**job, "requires": graph.list_requires(job["id"]), "sources": graph.list_job_evidence(job["id"])})
    return {"session_id": body.session_id, "graph_release": resume.get("graph_release"), "jobs": recommend_jobs(candidates, resume, limit=3)}


@app.post("/diagnose/simulate")
def diagnose_simulate(body: SimulateBody):
    resume = load_session(body.session_id)
    if resume is None:
        raise HTTPException(404, "session expired")
    selected_ids = [job_id for job_id in body.job_ids if job_id]
    if body.job_id and not selected_ids:
        selected_ids = [body.job_id]
    if not selected_ids or len(selected_ids) > 2:
        raise HTTPException(400, "请选择一至两个岗位")
    release = graph.public_release().get("id")
    if resume.get("graph_release") and release and resume["graph_release"] != release:
        raise HTTPException(409, "简历对应的岗位图谱版本已更新，请重新解析")
    selected = []
    for job_id in selected_ids:
        job = graph.get_public_job(job_id)
        if job is None or not graph.diagnostic_release(job_id)["ok"]:
            raise HTTPException(409, "岗位数据正在校验，暂不可模拟")
        selected.append({**job, "requires": graph.list_requires(job_id), "sources": graph.list_job_evidence(job_id)})
    allowed = set()
    simulations = []
    for job in selected:
        original = simulate_job(job["requires"], resume, [])
        allowed.update(original.get("allowed_skill_ids") or [])
    invalid = sorted(set(body.assumed_skill_ids) - allowed)
    if invalid:
        raise HTTPException(400, "只能模拟当前缺口、熟练级不足或要求组候选技能")
    for job in selected:
        simulations.append({"job_id": job["id"], "name": job.get("name") or job["id"], **simulate_job(job["requires"], resume, body.assumed_skill_ids)})
    index = {row["id"]: row for row in graph.list_skills(with_embed=False)}
    watching_ids = set(body.watching_skill_ids)
    watching = [{"skill_id": sid, "name": (index.get(sid) or {}).get("name") or sid} for sid in watching_ids]
    all_jobs = []
    for job in graph.list_jobs(domain=None, status=None, q=None):
        if not graph.diagnostic_release(job["id"])["ok"]:
            continue
        all_jobs.append({**job, "requires": graph.list_requires(job["id"]), "sources": graph.list_job_evidence(job["id"])})
    related = list(selected)
    for job in all_jobs:
        if job["id"] not in {item["id"] for item in related}:
            related.append(job)
        if len(related) == 3:
            break
    evidence = evidence_map(selected[0]["requires"], resume)
    return {
        "session_id": body.session_id,
        "graph_release": resume.get("graph_release"),
        "simulations": simulations,
        "evidence_map": {"job_id": selected[0]["id"], "relations": evidence},
        "migration_map": migration_map(related, resume),
        "market_signal_radar": market_signal_radar(watching, all_jobs, selected[0]["id"]),
        "watching_skill_ids": sorted(watching_ids),
    }


@app.post("/v1/diagnose/simulate")
def v1_diagnose_simulate(body: SimulateBody):
    return diagnose_simulate(body)


@app.post("/v1/diagnose/recommend")
def v1_diagnose_recommend(body: RecommendBody):
    return diagnose_recommend(body)


@app.post("/v1/diagnose")
def v1_diagnose(body: DiagnoseBody, request: Request):
    return diagnose(body=body, request=request)


@app.get("/discover")
def discover():
    return graph.discover_boards()


@app.get("/discover/{job_id}")
def discover_one(job_id: str):
    row = graph.discover_dossier(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@app.get("/feed")
def feed():
    return graph.build_feed()


class ApproveBody(BaseModel):
    payload: dict | None = None


class AdjudicateBody(BaseModel):
    file: str
    row_id: str
    deleted: list[str] = []
    added: list[dict] = []
    skip: bool = False


class PassthroughBody(BaseModel):
    enabled: bool = False


class ReleaseBody(BaseModel):
    period: str = ""
    metadata: dict = {}


class RetractionBody(BaseModel):
    reason: str = ""


class DiagnosticOverrideBody(BaseModel):
    reason: str = ""


class BulkApproveBody(BaseModel):
    override_reason: str = ""


class LoginBody(BaseModel):
    password: str


_admin_sessions: dict[str, tuple[float, str]] = {}
_login_attempts: dict[str, list[float]] = {}
ADMIN_SESSION_TTL = 3600


def _passwords_match(given: str, expected: str) -> bool:
    left = given.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right):
        hmac.compare_digest(right, right)
        return False
    return hmac.compare_digest(left, right)


def _require_admin(
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    expected = os.environ.get("ADMIN_PASSWORD", "change-me")
    session_id = request.cookies.get("admin_session")
    if session_id:
        row = _admin_sessions.get(session_id)
        if row and row[0] > time.time():
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                csrf = request.headers.get("X-CSRF-Token")
                if not csrf or not hmac.compare_digest(csrf, row[1]):
                    raise HTTPException(403, "csrf required")
            return
        _admin_sessions.pop(session_id, None)
    # Compatibility for scripts during the migration; browsers use the session cookie.
    if x_admin_password and _passwords_match(x_admin_password, expected):
        return
    raise HTTPException(401, "unauthorized")


@app.post("/admin/login")
def admin_login(body: LoginBody, request: Request, response: Response):
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    attempts = [stamp for stamp in _login_attempts.get(ip, []) if stamp > now - 60]
    if len(attempts) >= 5:
        raise HTTPException(429, "too many login attempts")
    _login_attempts[ip] = attempts + [now]
    expected = os.environ.get("ADMIN_PASSWORD", "change-me")
    if not _passwords_match(body.password, expected):
        raise HTTPException(401, "unauthorized")
    session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    _admin_sessions[session_id] = (now + ADMIN_SESSION_TTL, csrf)
    response.set_cookie("admin_session", session_id, max_age=ADMIN_SESSION_TTL, httponly=True,
                        secure=os.environ.get("ADMIN_COOKIE_SECURE", "1") == "1",
                        samesite="strict", path="/")
    response.set_cookie("admin_csrf", csrf, max_age=ADMIN_SESSION_TTL, httponly=False,
                        secure=os.environ.get("ADMIN_COOKIE_SECURE", "1") == "1",
                        samesite="strict", path="/")
    return {"expires_in": ADMIN_SESSION_TTL}


@app.post("/admin/logout")
def admin_logout(request: Request, response: Response):
    session_id = request.cookies.get("admin_session")
    if session_id:
        _admin_sessions.pop(session_id, None)
    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("admin_csrf", path="/")
    return {"ok": True}


@app.get("/admin/queue")
def admin_queue(
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    return graph.list_pending_events(include_auto_passed=passthrough_enabled())


@app.get("/admin/jobs/{job_id}/diagnostic-release")
def admin_diagnostic_release(
    job_id: str,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    if graph.get_any_job(job_id) is None:
        raise HTTPException(404, "not found")
    return graph.diagnostic_release(job_id)


@app.post("/admin/jobs/{job_id}/diagnostic-release")
def admin_override_diagnostic_release(
    job_id: str,
    body: DiagnosticOverrideBody,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    if graph.get_any_job(job_id) is None:
        raise HTTPException(404, "not found")
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(400, "放行理由不能为空")
    result = graph.diagnostic_release(job_id, override_reason=reason)
    if result["ok"]:
        graph.set_job_fields(job_id, diagnostic_override_reason=reason, diagnostic_override_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return result


@app.post("/admin/queue/{event_id}/approve")
def admin_approve(
    event_id: str,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    body: ApproveBody | None = None,
):
    _require_admin(request, x_admin_password)
    payload = body.payload if body else None
    try:
        return apply_event(event_id, review="approved", payload=payload)
    except KeyError:
        raise HTTPException(404, "not found") from None


@app.post("/admin/jobs/{job_id}/versions/{version_id}/approve-all")
def admin_approve_all(
    job_id: str,
    version_id: str,
    body: BulkApproveBody,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    if graph.get_any_job(job_id) is None:
        raise HTTPException(404, "not found")
    pending = []
    for event in graph.list_pending_events():
        payload = event.get("payload") or {}
        if payload.get("job_id") != job_id:
            continue
        if version_id not in {"pending", "latest"} and payload.get("version_id") not in {None, version_id}:
            continue
        pending.append(event)
    event_ids = sorted(event["id"] for event in pending)
    batch_id = "bulk-" + hashlib.sha256(json.dumps([job_id, version_id, event_ids], ensure_ascii=False).encode()).hexdigest()[:24]
    previous = graph.get_bulk_decision(batch_id)
    if previous:
        return {"ok": True, "idempotent": True, "batch_id": batch_id, "event_ids": event_ids, "audit": previous}
    if not pending:
        raise HTTPException(404, "没有待审提案")
    from app.pipeline.diagnostic_release import validate_diagnostic_release

    base = graph.list_requires(job_id)
    proposals = []
    unresolved = []
    for event in pending:
        payload = event.get("payload") or {}
        if payload.get("kind") != "requires_add":
            continue
        if payload.get("proposed_kind") not in {"required", "bonus"}:
            unresolved.append(payload.get("skill_name") or payload.get("skill_id") or event["id"])
            continue
        proposals.append({
            "skill_id": payload.get("skill_id"),
            "kind": payload.get("proposed_kind"),
            "group_id": payload.get("group_id"),
            "min_required": payload.get("min_required", 1),
            "sources": payload.get("sources") or [],
            "excerpt": payload.get("excerpt") or "",
        })
    if unresolved:
        raise HTTPException(409, json.dumps({"code": "kind_vote_unresolved", "items": unresolved}, ensure_ascii=False))
    check = validate_diagnostic_release(
        job_id=job_id,
        definition=graph.current_definition(job_id),
        requires=base + proposals,
        evidence=graph.list_job_evidence(job_id, include_retracted=True),
        previous_requires=[row for row in graph.list_requires_history(job_id) if row.get("valid_to")],
        override_reason=body.override_reason,
    )
    if not check["ok"]:
        anomaly_only = all(item.get("code", "").endswith("_anomaly") for item in check["errors"])
        status = 400 if anomaly_only and not body.override_reason.strip() else 409
        raise HTTPException(status, json.dumps({"code": "diagnostic_release_blocked", "errors": check["errors"]}, ensure_ascii=False))
    for event in pending:
        payload = event.get("payload") or {}
        if payload.get("proposed_kind") in {"required", "bonus"}:
            payload["approved_kind"] = payload["proposed_kind"]
        apply_event(event["id"], review="approved", payload=payload)
    actor = request.cookies.get("admin_session") or "shared-admin"
    graph.record_bulk_decision(batch_id=batch_id, job_id=job_id, version_id=version_id, event_ids=event_ids, actor=actor, reason=body.override_reason.strip())
    return {"ok": True, "idempotent": False, "batch_id": batch_id, "event_ids": event_ids, "audit": graph.get_bulk_decision(batch_id), "check": check}


@app.post("/admin/queue/{event_id}/reject")
def admin_reject(
    event_id: str,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    try:
        return apply_event(event_id, review="rejected")
    except KeyError:
        raise HTTPException(404, "not found") from None


@app.get("/admin/adjudicate/next")
def admin_adjudicate_next(
    request: Request,
    file: str = "jd",
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    from app.eval import adjudicate as adjudicate_mod

    try:
        return adjudicate_mod.next_row(file)
    except KeyError:
        raise HTTPException(400, "unknown file") from None


@app.post("/admin/adjudicate/decide")
def admin_adjudicate_decide(
    body: AdjudicateBody,
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    from app.eval import adjudicate as adjudicate_mod

    try:
        return adjudicate_mod.apply_decision(body.model_dump())
    except KeyError:
        raise HTTPException(404, "not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/admin/passthrough")
def admin_passthrough_get(
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    return {"enabled": passthrough_enabled()}


@app.put("/admin/passthrough")
def admin_passthrough_put(
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    body: PassthroughBody | None = None,
):
    _require_admin(request, x_admin_password)
    enabled = bool(body.enabled) if body else False
    set_passthrough(enabled)
    return {"enabled": passthrough_enabled()}


@app.post("/admin/releases")
def admin_publish_release(body: ReleaseBody, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    return graph.publish_graph_release(period=body.period, metadata=body.metadata)


@app.post("/admin/releases/{release_id}/rollback")
def admin_rollback_release(release_id: str, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    result = graph.rollback_graph_release(release_id)
    if result is None:
        raise HTTPException(404, "release not found")
    return result


@app.post("/admin/events/{event_id}/retract")
def admin_retract_event(event_id: str, body: RetractionBody, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    result = graph.retract_event(event_id, body.reason)
    if result is None:
        raise HTTPException(404, "event not found")
    return result


@app.post("/admin/evidence/{evidence_id}/retract")
def admin_retract_evidence(evidence_id: str, body: RetractionBody, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    if not graph.retract_evidence(evidence_id, body.reason):
        raise HTTPException(404, "evidence not found")
    return {"id": evidence_id, "retracted": True}


@app.get("/admin/ops/status")
def admin_ops_status(request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.ops_status import read as read_ops, stale as ops_stale
    return {"status": read_ops(), "stale": ops_stale()}


class PortalBody(BaseModel):
    name: str
    host: str


class PortalPatch(BaseModel):
    enabled: bool


def _data_dir() -> Path:
    from app.collectors.__main__ import default_data_dir

    return default_data_dir()


@app.get("/admin/portals")
def admin_portals(request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.collectors.ats import collect_busy, load_portals

    data_dir = _data_dir()
    return {"portals": load_portals(data_dir), "busy": collect_busy(data_dir)}


@app.post("/admin/portals")
def admin_add_portal(body: PortalBody, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.collectors.ats import enabled_count, load_portals, probe_feishu, save_portals

    host = (body.host or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    name = (body.name or "").strip()
    if not host or not name:
        raise HTTPException(400, "name and host required")
    data_dir = _data_dir()
    portals = load_portals(data_dir)
    if any((row.get("host") or "").lower() == host or row.get("key") == host for row in portals):
        raise HTTPException(409, "portal exists")
    if enabled_count(portals) >= 20:
        raise HTTPException(400, "at most 20 enabled portals")
    try:
        probe_feishu(host)
    except Exception as exc:
        raise HTTPException(400, f"probe failed: {exc}") from exc
    key = host.split(".")[0]
    while any(row.get("key") == key for row in portals):
        key = f"{key}-{len(portals)}"
    portals.append({"key": key, "type": "feishu", "name": name, "host": host, "enabled": True, "builtin": False})
    save_portals(data_dir, portals)
    return {"portals": portals}


@app.post("/admin/portals/{key}")
def admin_patch_portal(key: str, body: PortalPatch, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.collectors.ats import enabled_count, load_portals, save_portals

    data_dir = _data_dir()
    portals = load_portals(data_dir)
    row = next((item for item in portals if item.get("key") == key), None)
    if row is None:
        raise HTTPException(404, "portal not found")
    if body.enabled and not row.get("enabled") and enabled_count(portals) >= 20:
        raise HTTPException(400, "at most 20 enabled portals")
    row["enabled"] = body.enabled
    save_portals(data_dir, portals)
    return row


@app.post("/admin/portals/{key}/delete")
def admin_delete_portal(key: str, request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.collectors.ats import load_portals, save_portals

    data_dir = _data_dir()
    portals = load_portals(data_dir)
    row = next((item for item in portals if item.get("key") == key), None)
    if row is None:
        raise HTTPException(404, "portal not found")
    if row.get("builtin"):
        raise HTTPException(400, "builtin portal cannot be deleted")
    portals = [item for item in portals if item.get("key") != key]
    save_portals(data_dir, portals)
    return {"ok": True}


@app.post("/admin/collect")
def admin_collect(request: Request, x_admin_password: str | None = Header(default=None, alias="X-Admin-Password")):
    _require_admin(request, x_admin_password)
    from app.collectors.ats import collect_busy

    data_dir = _data_dir()
    if collect_busy(data_dir):
        raise HTTPException(409, "collect already running")
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    subprocess.Popen(
        [sys.executable, "-m", "app.collectors", "--daily"],
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
        start_new_session=True,
    )
    return {"ok": True}


def _sse_pack(event_id: str, fields: dict) -> str:
    raw = fields.get("payload") or "{}"
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        payload = {}
    body = {"id": fields.get("id"), "type": fields.get("type"), "payload": payload}
    return f"id: {event_id}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"


@app.get("/events/stream")
def events_stream(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    types: str | None = Query(None),
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    from app.collectors.sink import STREAM_KEY, connect_redis

    allowed = {part.strip() for part in (types or "").split(",") if part.strip()} or None
    start_id = last_event_id or "0-0"
    redis = connect_redis()

    def gen():
        cursor = start_id
        if start_id in {"0-0", "0", "-"}:
            try:
                recent = list(reversed(redis.xrevrange(STREAM_KEY, "+", "-", count=100)))
            except Exception:
                recent = []
            for event_id, fields in recent:
                cursor = event_id
                if allowed and fields.get("type") not in allowed:
                    continue
                yield _sse_pack(event_id, fields)
        while True:
            try:
                rows = redis.xread({STREAM_KEY: cursor}, block=15000, count=20)
            except Exception:
                yield ": ping\n\n"
                continue
            if not rows:
                yield ": ping\n\n"
                continue
            for _, entries in rows:
                for event_id, fields in entries:
                    cursor = event_id
                    if allowed and fields.get("type") not in allowed:
                        continue
                    yield _sse_pack(event_id, fields)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
