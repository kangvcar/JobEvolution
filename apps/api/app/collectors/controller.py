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
    seen: set[str] = set()
    while text and text not in seen:
        seen.add(text)
        for fmt in _DATE_FORMATS:
            width = 19 if "H" in fmt else 10
            try:
                return datetime.strptime(text[:width], fmt).isoformat()
            except ValueError:
                continue
        match = _DATE_IN_TEXT.search(text)
        if match is None:
            return ""
        nxt = match.group(1)
        if nxt == text:
            return ""
        text = nxt
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
        raw_hash = doc.get("simhash")
        if not raw_hash:
            continue
        try:
            value = int(str(raw_hash), 16)
        except (ValueError, TypeError):
            continue
        index.add(
            value,
            {
                "id": doc.get("id") or path.stem,
                "observed_at": doc.get("observed_at") or "",
                "fingerprint": doc.get("fingerprint") or "",
            },
        )


def _snapshot_dest(out_dir: Path, fingerprint: str) -> Path:
    return Path(out_dir) / f"{snapshot_id(fingerprint)}.json"


def _index_meta(snapshot: dict) -> dict:
    return {
        "id": snapshot["id"],
        "observed_at": snapshot.get("observed_at") or "",
        "fingerprint": snapshot.get("fingerprint") or "",
    }


def _commit_snapshot(out_dir: Path, record: RawRecord, body_hash: int, redis, on_evidence) -> dict:
    snapshot = _write_snapshot(out_dir, record, body_hash)
    emit_jd_ingested(redis, snapshot)
    redis.sadd(FP_KEY, record.fingerprint)
    if on_evidence is not None:
        on_evidence(snapshot)
    return snapshot


def _replace_snapshot(
    out_dir: Path,
    record: RawRecord,
    body_hash: int,
    redis,
    hit: dict,
    on_evidence,
) -> dict:
    old_id = hit.get("id") or ""
    old_fp = hit.get("fingerprint") or ""
    snapshot = _commit_snapshot(out_dir, record, body_hash, redis, on_evidence)
    old_path = Path(out_dir) / f"{old_id}.json"
    if old_id and old_path.exists() and old_path.name != f"{snapshot['id']}.json":
        old_path.unlink()
    if old_fp and old_fp != record.fingerprint and hasattr(redis, "srem"):
        redis.srem(FP_KEY, old_fp)
    hit.update(_index_meta(snapshot))
    return snapshot


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
        dest = _snapshot_dest(out_dir, record.fingerprint)
        fp_known = bool(redis.sismember(FP_KEY, record.fingerprint))
        # Skip only when the file and the Redis fingerprint both exist; leftover
        # SET members without a snapshot (or a crash before SADD) must rebuild.
        if dest.exists() and fp_known:
            skipped_fp += 1
            continue
        if dest.exists() and not fp_known:
            try:
                existing = json.loads(dest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = None
            if existing:
                emit_jd_ingested(redis, existing)
                redis.sadd(FP_KEY, record.fingerprint)
                if on_evidence is not None:
                    on_evidence(existing)
                skipped_fp += 1
                continue
        body_hash = simhash64(record.body)
        hit = index.find(body_hash)
        if hit is not None:
            if observed_sort_key(record.observed_at) < observed_sort_key(
                hit.get("observed_at") or ""
            ):
                _replace_snapshot(out_dir, record, body_hash, redis, hit, on_evidence)
                ingested += 1
                continue
            skipped_near += 1
            redis.sadd(FP_KEY, record.fingerprint)
            continue
        snapshot = _commit_snapshot(out_dir, record, body_hash, redis, on_evidence)
        index.add(body_hash, _index_meta(snapshot))
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
