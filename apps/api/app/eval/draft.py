"""ADR-0011: LLM 起草金标（只读原文），人工裁决。python -m app.eval draft"""

from __future__ import annotations

import json
import os
from datetime import date

from app.eval.io import read_jsonl
from app.eval.paths import eval_dir

PROMPT_VERSION = "gold-draft-v1"

SYSTEM = (
    "你是金标标注员。只从给出的原文里抽出明确写出的技能点：工具、语言、框架、平台、"
    "方法、领域知识。逐字或最小归一化地保留原文措辞；原文没写的不要推断，不要泛化成"
    "类目名。输出 JSON：{\"skills\": [\"原文措辞\", ...]}，没有则为空数组。"
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
    from app.llm.client import complete_json

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
    notes["gold_draft"] = {
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "date": date.today().isoformat(),
        "prompt": PROMPT_VERSION,
        "skills": [str(s) for s in skills] if isinstance(skills, list) else [],
    }
    row["notes"] = notes
    return row


def _write_jsonl(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    for name in ("jd.jsonl", "resume.jsonl"):
        path = eval_dir() / name
        rows = [_draft_one(row) for row in read_jsonl(path)]
        _write_jsonl(path, rows)
        total = sum(len(row["notes"]["gold_draft"]["skills"]) for row in rows)
        print(json.dumps({"file": name, "rows": len(rows), "draft_skills": total}, ensure_ascii=False))
    return 0
