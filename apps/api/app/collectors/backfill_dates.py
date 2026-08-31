"""Fill missing snapshot observed_at values from source CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.collectors.controller import (
    is_scrape_calendar,
    observed_at_for,
    table_year,
    uniform_parsed_day,
)
from app.collectors.normalize import fingerprint_for
from app.collectors.source import SOURCE_CHANNEL, field_map, map_row, discover_tables, iter_records

DATE_COLUMN = "发布日期"


def _table_ignore_parsed(table: Path, batch, year: int | None) -> bool:
    published = [record.published_at for record in batch]
    try:
        with table.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            names = reader.fieldnames or []
            if "publish_detail" in names:
                blobs = [row.get("publish_detail") or "" for row in reader]
                if is_scrape_calendar(blobs):
                    return True
    except OSError:
        pass
    return uniform_parsed_day(published, year)


def backfill(data_dir: Path, out_dir: Path) -> dict[str, int]:
    records: dict[str, tuple[str, int, bool]] = {}
    rewrite: set[str] = set()
    skipped_tables = 0
    for table in discover_tables(data_dir):
        year = table_year(table.name)
        if year is None:
            skipped_tables += 1
            continue
        batch = list(iter_records(table))
        ignore_parsed = _table_ignore_parsed(table, batch, year)
        for record in batch:
            fingerprint = fingerprint_for(
                record.source, record.job_id, record.company, record.title, record.city
            )
            records.setdefault(fingerprint, (record.published_at, year, ignore_parsed))
            if ignore_parsed:
                rewrite.add(fingerprint)

    filled = unmatched = skipped = 0
    for path in sorted(Path(out_dir).glob("jd-*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        fingerprint = doc.get("fingerprint") or ""
        source = records.get(fingerprint)
        if source is None:
            if not doc.get("observed_at"):
                unmatched += 1
            continue
        published_at, year, ignore_parsed = source
        if doc.get("observed_at") and fingerprint not in rewrite:
            continue
        value = observed_at_for(
            published_at, fingerprint, year, ignore_parsed=ignore_parsed
        )
        if doc.get("observed_at") == value:
            continue
        doc["observed_at"] = value
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        filled += 1
    return {"filled": filled, "unmatched": unmatched, "skipped": skipped + skipped_tables}


def _row_date(
    row: dict, mapping: dict[str, str], year: int, *, ignore_parsed: bool = False
) -> str:
    record = map_row(row, mapping)
    if record is None:
        return ""
    fingerprint = fingerprint_for(
        SOURCE_CHANNEL, record.job_id, record.company, record.title, record.city
    )
    return observed_at_for(
        record.published_at, fingerprint, year, ignore_parsed=ignore_parsed
    )[:10]


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
        if "招聘发布日期" in fieldnames:
            skipped += 1
            continue
        published = []
        for row in rows:
            record = map_row(row, mapping)
            published.append(record.published_at if record else "")
        blobs = (
            [row.get("publish_detail") or "" for row in rows]
            if "publish_detail" in fieldnames
            else published
        )
        ignore_parsed = is_scrape_calendar(blobs) or uniform_parsed_day(published, year)
        if DATE_COLUMN in fieldnames and not ignore_parsed:
            skipped += 1
            continue
        out_fields = fieldnames if DATE_COLUMN in fieldnames else [*fieldnames, DATE_COLUMN]
        for row in rows:
            row[DATE_COLUMN] = _row_date(row, mapping, year, ignore_parsed=ignore_parsed)
        dest = table.with_suffix(".csv.tmp")
        with dest.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=out_fields,
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
