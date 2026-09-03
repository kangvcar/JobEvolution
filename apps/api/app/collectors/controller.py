"""Dedup local JD records and write snapshots."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from app.collectors.domain import classify_domain
from app.collectors.normalize import (
    fingerprint_for,
    is_channel_name,
    normalize_company,
)
from app.collectors.simhash import SimhashIndex, format_simhash, simhash64
from app.collectors.sink import BODY_KEY, FP_KEY, emit_jd_ingested
from app.collectors.source import RawRecord, discover_tables, iter_records

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
)
_DATE_IN_TEXT = re.compile(r"(\d{4}[-/.]\d{2}[-/.]\d{2})")
_MONTH_DAY_IN_TEXT = re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})发布")
_YEAR_IN_TABLE = re.compile(r"(\d{4})\.csv$", re.IGNORECASE)


def parse_observed_at(value: str, year: int | None = None) -> str:
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
        if match is not None:
            nxt = match.group(1)
            if nxt == text:
                return ""
            text = nxt
            continue
        if year is None:
            return ""
        match = _MONTH_DAY_IN_TEXT.search(text)
        if match is None:
            return ""
        try:
            return datetime(year, int(match.group(1)), int(match.group(2))).isoformat()
        except ValueError:
            return ""
    return ""


def table_year(table: str) -> int | None:
    match = _YEAR_IN_TABLE.search(table or "")
    return int(match.group(1)) if match else None


def stable_observed_at(fingerprint: str, year: int) -> str:
    start = datetime(year, 1, 1)
    span = (datetime(year, 12, 28) - start).days + 1
    offset = int(fingerprint[:16], 16) % span
    return (start + timedelta(days=offset)).isoformat()


def observed_at_for(
    published_at: str,
    fingerprint: str,
    year: int | None,
    *,
    ignore_parsed: bool = False,
) -> str:
    if not ignore_parsed:
        parsed = parse_observed_at(published_at, year)
        if parsed or year is None:
            return parsed
    if year is None:
        return ""
    return stable_observed_at(fingerprint, year)


def uniform_parsed_day(published_at_values: list[str], year: int | None) -> bool:
    if year is None:
        return False
    days = [day for v in published_at_values if (day := parse_observed_at(v, year)[:10])]
    return len(days) >= 2 and len(set(days)) == 1


def is_scrape_calendar(values: list[str]) -> bool:
    """True when dates look like a crawl stamp: MM-DD发布 clustered in a short window, no ISO year."""
    days: list[datetime] = []
    for value in values:
        text = value or ""
        if _DATE_IN_TEXT.search(text):
            return False
        match = _MONTH_DAY_IN_TEXT.search(text)
        if match is None:
            continue
        try:
            days.append(datetime(2020, int(match.group(1)), int(match.group(2))))
        except ValueError:
            continue
    if len(days) < 50:
        return False
    return (max(days) - min(days)).days <= 31


def observed_sort_key(iso: str) -> datetime:
    if not iso:
        return datetime.max
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return datetime.max


def snapshot_id(fingerprint: str) -> str:
    return "jd-" + fingerprint[:16]


def posting_key(source: str, job_id: str) -> str:
    return sha256(f"{source}\0{job_id}".encode("utf-8")).hexdigest()


def ats_fingerprint(source: str, job_id: str, simhash: str) -> str:
    return sha256(f"{source}{job_id}{simhash}".encode("utf-8")).hexdigest()


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
                "source": doc.get("source") or "",
                "job_id": doc.get("job_id") or "",
                "simhash": str(raw_hash),
            },
        )


def _snapshot_dest(out_dir: Path, fingerprint: str) -> Path:
    return Path(out_dir) / f"{snapshot_id(fingerprint)}.json"


def _index_meta(snapshot: dict) -> dict:
    return {
        "id": snapshot["id"],
        "observed_at": snapshot.get("observed_at") or "",
        "fingerprint": snapshot.get("fingerprint") or "",
        "source": snapshot.get("source") or "",
        "job_id": snapshot.get("job_id") or "",
        "simhash": snapshot.get("simhash") or "",
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
    if old_fp and old_fp != record.fingerprint:
        redis.srem(FP_KEY, old_fp)
    if on_evidence is not None and old_id and old_id != snapshot["id"]:
        on_evidence.drop(old_id)
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
        "url": record.url,
    }
    dest = Path(out_dir) / f"{sid}.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dest)
    return doc


def _prepare(record: RawRecord, *, ignore_parsed: bool = False) -> RawRecord | None:
    if not record.body:
        return None
    if not record.domain:
        domain = classify_domain(record.title)
        if domain is None:
            return None
        record.domain = domain
    if not record.fingerprint:
        record.fingerprint = fingerprint_for(
            record.source,
            record.job_id,
            record.company,
            record.title,
            record.city,
        )
    record.observed_at = observed_at_for(
        record.published_at,
        record.fingerprint,
        table_year(record.table),
        ignore_parsed=ignore_parsed,
    )
    return record


def ingest_records(
    records: list[RawRecord],
    *,
    out_dir: Path,
    redis,
    on_evidence=None,
    index: SimhashIndex | None = None,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if index is None:
        index = SimhashIndex()
        _load_existing(out_dir, redis, index)

    skipped_fp = 0
    skipped_near = 0
    ingested = 0
    for record in records:
        if not (record.body or "").strip():
            continue
        if not record.observed_at:
            record.observed_at = record.published_at or datetime.now().isoformat()
        body_hash = simhash64(record.body)
        body_hex = format_simhash(body_hash)
        if record.source == "ats" and record.job_id:
            pkey = posting_key(record.source, record.job_id)
            prev = redis.hget(BODY_KEY, pkey)
            if prev == body_hex:
                skipped_fp += 1
                continue
            record.fingerprint = ats_fingerprint(record.source, record.job_id, body_hex)
        dest = _snapshot_dest(out_dir, record.fingerprint)
        fp_known = bool(redis.sismember(FP_KEY, record.fingerprint))
        if record.source != "ats" and dest.exists() and fp_known:
            skipped_fp += 1
            continue
        if record.source != "ats" and dest.exists() and not fp_known:
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
        hit = index.find(body_hash)
        if hit is not None and record.source == "ats" and record.job_id:
            same_posting = hit.get("source") == "ats" and hit.get("job_id") == record.job_id
            if same_posting and hit.get("simhash") == body_hex:
                skipped_fp += 1
                continue
            if same_posting:
                hit = None
        if hit is not None:
            if observed_sort_key(record.observed_at) < observed_sort_key(
                hit.get("observed_at") or ""
            ):
                _replace_snapshot(out_dir, record, body_hash, redis, hit, on_evidence)
                ingested += 1
                if record.source == "ats" and record.job_id:
                    redis.hset(BODY_KEY, posting_key(record.source, record.job_id), body_hex)
                continue
            skipped_near += 1
            redis.sadd(FP_KEY, record.fingerprint)
            if record.source == "ats" and record.job_id:
                redis.hset(BODY_KEY, posting_key(record.source, record.job_id), body_hex)
            continue
        snapshot = _commit_snapshot(out_dir, record, body_hash, redis, on_evidence)
        index.add(body_hash, _index_meta(snapshot))
        ingested += 1
        if record.source == "ats" and record.job_id:
            redis.hset(BODY_KEY, posting_key(record.source, record.job_id), body_hex)
    return {
        "skipped_fingerprint": skipped_fp,
        "skipped_near_dup": skipped_near,
        "ingested": ingested,
    }


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
        batch = list(iter_records(table))
        ignore_parsed = uniform_parsed_day(
            [record.published_at for record in batch], table_year(table.name)
        )
        for record in batch:
            read += 1
            if not record.body:
                dropped_body += 1
                continue
            ready = _prepare(record, ignore_parsed=ignore_parsed)
            if ready is None:
                dropped_domain += 1
                continue
            prepared.append(ready)

    prepared.sort(key=lambda rec: (observed_sort_key(rec.observed_at), rec.fingerprint))
    written = ingest_records(prepared, out_dir=out_dir, redis=redis, on_evidence=on_evidence, index=index)

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
        "skipped_fingerprint": written["skipped_fingerprint"],
        "skipped_near_dup": written["skipped_near_dup"],
        "ingested": written["ingested"],
        "paths": len(paths),
        "by_domain": {key: by_domain[key] for key in ("ai", "data", "system", "iot")},
        "independent_sources": len(sources),
    }
