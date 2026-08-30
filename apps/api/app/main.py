from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import graph


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
):
    return graph.list_jobs(domain=domain, status=status, q=q)


@app.get("/jobs/{job_id}")
def job_detail(job_id: str):
    row = graph.get_public_job(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    return row


@app.get("/graph/jobs/{job_id}")
def job_slice(job_id: str):
    row = graph.get_public_job(job_id)
    if row is None:
        raise HTTPException(404, "not found")
    return {
        "job": row,
        "categories": [],
        "skills": [],
        "requires": [],
        "period_delta": {"added": [], "promoted": [], "expired": []},
    }
