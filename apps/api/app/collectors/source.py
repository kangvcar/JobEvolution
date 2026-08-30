"""Discover local JD tables and map heterogeneous columns onto one record."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 8 * 1024 * 1024))

# `岗位名` before `岗位` so IT headers do not bind title to the shorter column.
COLUMN_ALIASES = {
    "company": ("企业名称", "company", "公司名称", "company_name", "公司"),
    "title": ("招聘岗位", "name", "岗位名", "job_name", "岗位"),
    "body": ("职位描述", "demand", "岗位描述", "job_duty", "岗位要求"),
    "published_at": ("招聘发布日期", "发布日期", "publish_detail"),
    "city": ("工作城市", "location", "工作地区", "job_city", "城市"),
    "channel": ("来源",),
    "job_id": ("岗位id",),
}

REQUIRED_ROLES = ("company", "title", "body")
SOURCE_CHANNEL = "local"
_SKIP_DIR_NAMES = frozenset({"jd", "eval"})


@dataclass
class RawRecord:
    company: str
    title: str
    body: str
    published_at: str
    city: str
    channel: str
    job_id: str
    source: str = SOURCE_CHANNEL
    domain: str = ""
    fingerprint: str = ""
    observed_at: str = ""
    table: str = ""


def field_map(fieldnames: list[str] | None) -> dict[str, str] | None:
    names = set(fieldnames or [])
    mapping: dict[str, str] = {}
    for role, aliases in COLUMN_ALIASES.items():
        hit = next((alias for alias in aliases if alias in names), None)
        if hit is None:
            if role in REQUIRED_ROLES:
                return None
            continue
        mapping[role] = hit
    return mapping


def discover_tables(data_dir: Path) -> list[Path]:
    root = Path(data_dir)
    if not root.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(root.rglob("*.csv")):
        rel_parts = path.relative_to(root).parts[:-1]
        if any(part in _SKIP_DIR_NAMES for part in rel_parts):
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                continue
        if field_map(header) is None:
            continue
        found.append(path)
    return found


def _cell(row: dict, mapping: dict[str, str], role: str) -> str:
    key = mapping.get(role)
    if not key:
        return ""
    return (row.get(key) or "").strip()


def map_row(row: dict, mapping: dict[str, str] | None = None) -> RawRecord | None:
    mapping = mapping if mapping is not None else field_map(list(row.keys()))
    if mapping is None:
        return None
    return RawRecord(
        company=_cell(row, mapping, "company"),
        title=_cell(row, mapping, "title"),
        body=_cell(row, mapping, "body"),
        published_at=_cell(row, mapping, "published_at"),
        city=_cell(row, mapping, "city"),
        channel=_cell(row, mapping, "channel"),
        job_id=_cell(row, mapping, "job_id"),
        source=SOURCE_CHANNEL,
    )


def iter_records(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        mapping = field_map(reader.fieldnames)
        if mapping is None:
            return
        for row in reader:
            record = map_row(row, mapping)
            if record is None:
                continue
            record.table = path.name
            yield record
