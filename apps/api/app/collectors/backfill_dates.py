"""Fill missing snapshot observed_at values from source CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.collectors.controller import observed_at_for, table_year
from app.collectors.normalize import fingerprint_for
from app.collectors.source import SOURCE_CHANNEL, field_map, map_row, discover_tables, iter_records

DATE_COLUMN = "发布日期"
_CANONICAL_DATE_HEADERS = ("招聘发布日期", "发布日期")


def backfill(data_dir: Path, out_dir: Path) -> dict[str, int]:
    records: dict[str, tuple[str, int]] = {}
    skipped_tables = 0
    for table in discover_tables(data_dir):
        year = table_year(table.name)
        if year is None:
            skipped_tables += 1
            continue
        for record in iter_records(table):
            fingerprint = fingerprint_for(
                record.source, record.job_id, record.company, record.title, record.city
            )
            records.setdefault(fingerprint, (record.published_at, year))

    filled = unmatched = skipped = 0
    for path in sorted(Path(out_dir).glob("jd-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        if doc.get("observed_at"):
            continue
        fingerprint = doc.get("fingerprint") or ""
        source = records.get(fingerprint)
        if source is None:
            unmatched += 1
            continue
        published_at, year = source
        doc["observed_at"] = observed_at_for(published_at, fingerprint, year)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        filled += 1
    return {"filled": filled, "unmatched": unmatched, "skipped": skipped + skipped_tables}


def _row_date(row: dict, mapping: dict[str, str], year: int) -> str:
    record = map_row(row, mapping)
    if record is None:
        return ""
    fingerprint = fingerprint_for(
        SOURCE_CHANNEL, record.job_id, record.company, record.title, record.city
    )
    return observed_at_for(record.published_at, fingerprint, year)[:10]


def backfill_tables(data_dir: Path) -> dict[str, int]:
    filled = skipped = 0
    for table in discover_tables(data_dir):
        year = table_year(table.name)
        if year is None:
            skipped += 1
            continue
        with table.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            mapping = field_map(fieldnames)
            rows = list(reader)
        if mapping is None:
            skipped += 1
            continue
        if any(name in fieldnames for name in _CANONICAL_DATE_HEADERS):
            skipped += 1
            continue
        for row in rows:
            row[DATE_COLUMN] = _row_date(row, mapping, year)
        dest = table.with_suffix(".csv.tmp")
        with dest.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[*fieldnames, DATE_COLUMN],
                lineterminator="\r\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        dest.replace(table)
        filled += 1
    return {"tables": filled, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill missing JD snapshot dates")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--tables", action="store_true", help="add 发布日期 column to source CSVs")
    args = parser.parse_args(argv)
    if args.tables:
        stats = backfill_tables(args.data_dir)
    else:
        stats = backfill(args.data_dir, args.out_dir or args.data_dir / "jd")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
