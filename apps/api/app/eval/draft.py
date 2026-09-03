"""ADR-0011: LLM 起草金标（只读原文），人工裁决。python -m app.eval draft"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from app.collectors.controller import write_json_atomic
from app.eval.io import read_jsonl
from app.eval.paths import eval_dir
from app.pipeline.constants import SKILL_DEFINITION

PROMPT_VERSION = "gold-draft-v1"
CHECKPOINT_FILE = "draft.checkpoint.json"

SYSTEM = (
    f"你是金标标注员。{SKILL_DEFINITION}"
    "保留原文措辞。输出 JSON：{\"skills\": [\"原文措辞\", ...]}，没有则为空数组。"
)


def _draft_text(row: dict) -> str:
    path = row.get("path")
    if path:
        from app.pipeline.sections import split_sections

        body = json.loads(open(path, encoding="utf-8").read()).get("body") or ""
        parts = split_sections(body)
        text = f"{parts['duty']}\n{parts['requirement']}".strip()
        return text or body
    return row.get("text") or ""


def _draft_one(row: dict) -> dict:
    from app.llm.client import _provider_config, complete_json

    text = _draft_text(row)
    payload = complete_json(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text},
        ]
    )
    skills = payload.get("skills") if isinstance(payload, dict) else None
    notes = row.get("notes")
    notes = dict(notes) if isinstance(notes, dict) else {}
    provider, _, _, model = _provider_config()
    notes["gold_draft"] = {
        "provider": provider,
        "model": model,
        "date": date.today().isoformat(),
        "prompt": PROMPT_VERSION,
        "skills": [str(s) for s in skills] if isinstance(skills, list) else [],
    }
    row["notes"] = notes
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _has_current_draft(row: dict) -> bool:
    return (row.get("notes") or {}).get("gold_draft", {}).get("prompt") == PROMPT_VERSION


def _write_checkpoint(**state) -> None:
    write_json_atomic(eval_dir() / CHECKPOINT_FILE, {"version": 1, **state})


def _draft_file(name: str) -> dict:
    path = eval_dir() / name
    rows = read_jsonl(path)
    completed = sum(_has_current_draft(row) for row in rows)
    failures = []
    _write_checkpoint(status="running", file=name, current="", completed=completed, total=len(rows), failures=failures)
    for index, row in enumerate(rows):
        if _has_current_draft(row):
            continue
        current = row.get("id") or str(index)
        _write_checkpoint(
            status="running", file=name, current=current, completed=completed, total=len(rows), failures=failures
        )
        try:
            rows[index] = _draft_one(row)
            _write_jsonl(path, rows)
        except Exception as exc:
            failures.append({"id": current, "error": f"{type(exc).__name__}: {exc}"[:300]})
            _write_checkpoint(
                status="partial", file=name, current="", completed=completed, total=len(rows), failures=failures
            )
            continue
        completed += 1
        _write_checkpoint(
            status="running", file=name, current="", completed=completed, total=len(rows), failures=failures
        )
    total = sum(len((row.get("notes") or {}).get("gold_draft", {}).get("skills", [])) for row in rows)
    _write_checkpoint(
        status="done" if not failures else "partial", file=name, current="", completed=completed,
        total=len(rows), failures=failures
    )
    return {"file": name, "rows": len(rows), "draft_skills": total, "failed": len(failures)}


def main() -> int:
    results = []
    for name in ("jd.jsonl", "resume.jsonl"):
        result = _draft_file(name)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    failed = sum(result["failed"] for result in results)
    _write_checkpoint(status="completed" if not failed else "partial", file="", current="", completed=0, total=0, failed=failed)
    return 1 if failed else 0
