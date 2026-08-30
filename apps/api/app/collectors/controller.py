"""Dedup local JD records and write snapshots."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.collectors.domain import classify_domain
from app.collectors.normalize import (
    fingerprint_for,
    is_channel_name,
    normalize_company,
)
from app.collectors.simhash import SimhashIndex, format_simhash, simhash64
from app.collectors.sink import FP_KEY, emit_jd_ingested
from app.collectors.source import RawRecord, discover_tables, iter_records

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
)
_DATE_IN_TEXT = re.compile(r"(\d{4}[-/.]\d{2}[-/.]\d{2})")


def parse_observed_at(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for fmt in _DATE_FORMATS:
        width = 19 if "H" in fmt else 10
        try:
            return datetime.strptime(text[:width], fmt).isoformat()
        except ValueError:
            continue
    match = _DATE_IN_TEXT.search(text)
    if match:
        return parse_observed_at(match.group(1))
    return ""


def observed_sort_key(iso: str) -> datetime:
    if not iso:
        return datetime.max
    return datetime.fromisoformat(iso)


def snapshot_id(fingerprint: str) -> str:
    return "jd-" + fingerprint[:16]


def list_snapshot_paths(out_dir: Path) -> list[Path]:
    return sorted(path for path in Path(out_dir).glob("*.json") if path.is_file())


def independent_companies(snapshots: list[dict]) -> set[str]:
    names: set[str] = set()
    for snap in snapshots:
        company = snap.get("company") or normalize_company(snap.get("company_raw") or "")
        if not company or is_channel_name(company):
            continue
        names.add(company)
    return names


def _load_existing(out_dir: Path, redis, index: SimhashIndex) -> None:
    for path in list_snapshot_paths(out_dir):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        fp = doc.get("fingerprint")
        if fp:
            redis.sadd(FP_KEY, fp)
        raw_hash = doc.get("simhash")
        if raw_hash:
            index.add(int(str(raw_hash), 16), doc.get("id") or path.stem)


def _write_snapshot(out_dir: Path, record: RawRecord, body_hash: int) -> dict:
    sid = snapshot_id(record.fingerprint)
    relpath = f"data/jd/{sid}.json"
    company = normalize_company(record.company)
    doc = {
        "id": sid,
        "path": relpath,
        "source": record.source,
        "company": company,
        "company_raw": record.company,
        "title": record.title,
        "body": record.body,
        "city": record.city,
        "published_at": record.published_at,
        "observed_at": record.observed_at,
        "channel": record.channel,
        "job_id": record.job_id,
        "fingerprint": record.fingerprint,
        "simhash": format_simhash(body_hash),
        "domain": record.domain,
    }
    dest = Path(out_dir) / f"{sid}.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dest)
    return doc


def _prepare(record: RawRecord) -> RawRecord | None:
    if not record.body:
        return None
    domain = classify_domain(record.title)
    if domain is None:
        return None
    record.domain = domain
    record.observed_at = parse_observed_at(record.published_at)
    record.fingerprint = fingerprint_for(
        record.source,
        record.job_id,
        record.company,
        record.title,
        record.city,
    )
    return record


def run_ingest(*, data_dir: Path, out_dir: Path, redis, on_evidence=None) -> dict:
    data_dir = Path(data_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = SimhashIndex()
    _load_existing(out_dir, redis, index)

    dropped_body = 0
    dropped_domain = 0
    read = 0
    tables = discover_tables(data_dir)
    prepared: list[RawRecord] = []
    for table in tables:
        for record in iter_records(table):
            read += 1
            if not record.body:
                dropped_body += 1
                continue
            ready = _prepare(record)
            if ready is None:
                dropped_domain += 1
                continue
            prepared.append(ready)

    prepared.sort(key=lambda rec: (observed_sort_key(rec.observed_at), rec.fingerprint))

    skipped_fp = 0
    skipped_near = 0
    ingested = 0
    for record in prepared:
        if redis.sismember(FP_KEY, record.fingerprint):
            skipped_fp += 1
            continue
        body_hash = simhash64(record.body)
        if index.find(body_hash) is not None:
            skipped_near += 1
            redis.sadd(FP_KEY, record.fingerprint)
            continue
        snapshot = _write_snapshot(out_dir, record, body_hash)
        emit_jd_ingested(redis, snapshot)
        redis.sadd(FP_KEY, record.fingerprint)
        index.add(body_hash, snapshot["id"])
        if on_evidence is not None:
            on_evidence(snapshot)
        ingested += 1

    paths = list_snapshot_paths(out_dir)
    snapshots = []
    by_domain: Counter[str] = Counter()
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        snapshots.append(doc)
        by_domain[doc.get("domain") or ""] += 1

    sources = independent_companies(snapshots)
    return {
        "tables": len(tables),
        "read": read,
        "dropped_body": dropped_body,
        "dropped_domain": dropped_domain,
        "skipped_fingerprint": skipped_fp,
        "skipped_near_dup": skipped_near,
        "ingested": ingested,
        "paths": len(paths),
        "by_domain": {key: by_domain[key] for key in ("ai", "data", "system", "iot")},
        "independent_sources": len(sources),
    }
