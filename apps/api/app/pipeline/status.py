from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from app.collectors.normalize import is_channel_name, normalize_company
from app.pipeline.constants import (
    EMERGING_SOURCES,
    EMERGING_WINDOW_DAYS,
    FORMED_MONTHS,
    FORMED_SOURCES,
)
from app.targets import JOB_TARGET_NAMES


def job_id_for(name: str) -> str:
    return "job-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def _parse_at(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def source_stats(rows: list[dict]) -> tuple[int, int, int]:
    """Return n_window, n_total, span_days from evidence rows with company+observed_at."""
    points = []
    for row in rows:
        company = normalize_company(row.get("company") or "")
        if not company or is_channel_name(company):
            continue
        at = _parse_at(row.get("observed_at") or "")
        if at is None:
            continue
        points.append((company, at))
    if not points:
        return 0, 0, 0
    latest = max(at for _, at in points)
    window_start = latest - timedelta(days=EMERGING_WINDOW_DAYS)
    total = {company for company, _ in points}
    window = {company for company, at in points if at >= window_start}
    earliest = min(at for _, at in points)
    span = (latest - earliest).days
    return len(window), len(total), span


def compute_status(
    *,
    n_window: int,
    n_total: int,
    span_days: int,
    definition_passed: bool,
    judged_new: bool,
) -> str:
    if definition_passed and (
        n_total >= FORMED_SOURCES or span_days >= FORMED_MONTHS * 30
    ):
        return "formed"
    if judged_new and n_window >= EMERGING_SOURCES:
        return "emerging"
    return "candidate"


def is_target_job(name: str) -> bool:
    return (name or "") in JOB_TARGET_NAMES


def refresh_job_status(job_id: str) -> str:
    from app import graph

    job = graph.get_any_job(job_id)
    if job is None:
        return "candidate"
    if graph.has_alias_out(job_id):
        graph.set_job_fields(job_id, status="candidate")
        return "candidate"
    n_window, n_total, span_days = source_stats(graph.list_job_evidence(job_id))
    judged_new = job.get("judged") == "new" or is_target_job(job.get("name") or "")
    status = compute_status(
        n_window=n_window,
        n_total=n_total,
        span_days=span_days,
        definition_passed=graph.definition_passed(job_id),
        judged_new=judged_new,
    )
    graph.set_job_fields(job_id, status=status)
    return status
