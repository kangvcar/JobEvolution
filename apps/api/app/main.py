import hmac
import os
from contextlib import asynccontextmanager

from pydantic import BaseModel

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import graph
from app.matching.report import neighbor_name, wrap_report
from app.matching.resume import ResumeError, extract_text, parse_resume
from app.matching.session import load as load_session
from app.matching.session import save as save_session
from app.pipeline.gate import apply_event, passthrough_enabled, set_passthrough
from app.pipeline.status import job_id_for


@asynccontextmanager
async def lifespan(_: FastAPI):
    graph.init_graph()
    yield
    graph.close_graph()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse(
        {"error": str(exc.detail), "detail": None},
        status_code=exc.status_code,
    )


@app.get("/meta")
def meta():
    return {"domains": graph.list_domains()}


@app.get("/jobs")
def jobs(
    domain: str | None = None,
    status: str | None = None,
    q: str | None = Query(None),
    category: str | None = Query(None),
    level: str | None = Query(None, pattern="^(junior|mid|senior)$"),
):
    return graph.list_jobs(domain=domain, status=status, q=q, category=category, level=level)


@app.get("/jobs/{job_id}")
def job_detail(job_id: str):
    row = graph.get_public_job(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    row["events"] = graph.list_job_events(job_id)
    evidence = graph.list_job_evidence(job_id)
    row["sources"] = sorted({item["company"] for item in evidence if item.get("company")})
    return row


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
        "period_delta": graph.period_delta(job_id),
    }


class DiagnoseBody(BaseModel):
    job_id: str
    session_id: str | None = None


@app.post("/sessions")
async def create_session(file: UploadFile = File(...)):
    data = await file.read()
    try:
        text = extract_text(data, file.filename or "")
    except ResumeError as exc:
        raise HTTPException(400, exc.detail) from exc
    parsed = parse_resume(text, graph.list_skills())
    session_id = save_session(
        {
            "preview_text": text[:4000],
            "skills": parsed["skills"],
            "experience": parsed["experience"],
            "education": parsed["education"],
            "filename": file.filename,
        }
    )
    return {
        "session_id": session_id,
        "skills": parsed["skills"],
        "preview_text": text[:2000],
        "experience": parsed["experience"],
        "education": parsed["education"],
    }


@app.post("/diagnose")
def diagnose(body: DiagnoseBody):
    job = graph.get_any_job(body.job_id)
    if job is None:
        raise HTTPException(404, "not found")
    if job.get("status") == "candidate":
        raise HTTPException(400, "candidate")
    resume = load_session(body.session_id or "")
    if resume is None:
        raise HTTPException(404, "session expired")
    resume["session_id"] = body.session_id
    requires = graph.list_requires(body.job_id)
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
    return wrap_report(
        job=job,
        requires=requires,
        resume=resume,
        neighbor=neighbor,
        watching=watching,
        slice_data={"categories": graph.job_slice(body.job_id)["categories"], "requires": requires, "period_delta": graph.period_delta(body.job_id)},
    )


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


class PassthroughBody(BaseModel):
    enabled: bool = False


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
    given = x_admin_password or request.cookies.get("admin_password") or ""
    if not _passwords_match(given, expected):
        raise HTTPException(401, "unauthorized")


@app.get("/admin/queue")
def admin_queue(
    request: Request,
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
):
    _require_admin(request, x_admin_password)
    return graph.list_pending_events(include_auto_passed=passthrough_enabled())


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
