"""ADR-0011 金标裁决：LLM 起草（draft.py），人裁决。CLI 与管理页共用 prep/apply。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import date

from app.eval.io import read_jsonl
from app.eval.paths import eval_dir
from app.eval.freeze import load_freeze
from app.pipeline.align import align_skill
from app.llm.embed import embed

FILES = {"jd": "jd.jsonl", "resume": "resume.jsonl"}
_index_cache: list[dict] | None = None


def _vocab() -> list[dict]:
    global _index_cache
    if _index_cache is None:
        skills = json.loads((eval_dir() / "skills.json").read_text(encoding="utf-8"))
        vectors = embed([s["name"] for s in skills])
        for skill, vec in zip(skills, vectors, strict=True):
            skill["embedding"] = vec
        _index_cache = skills
    return _index_cache


def _names(by_id: dict, sid: str) -> list[str]:
    skill = by_id.get(sid) or {}
    return [skill.get("name") or "", *(skill.get("synonyms") or [])]


def _row_text(row: dict) -> str:
    path = row.get("path")
    if path:
        from app.pipeline.sections import split_sections

        body = json.loads(open(path, encoding="utf-8").read()).get("body") or ""
        parts = split_sections(body)
        return f"{parts['duty']}\n{parts['requirement']}".strip() or body
    return row.get("text") or ""


def _mark_done(row: dict, *, skipped: bool, deleted: list[str], added: list[str]) -> None:
    row.setdefault("notes", {})["adjudicated"] = {
        "date": date.today().isoformat(),
        "skipped": skipped,
        "deleted": sorted(deleted),
        "added": added,
    }


def prep_row(row: dict, index: list[dict], by_id: dict, cut: float) -> dict:
    text = _row_text(row)
    draft = (row.get("notes") or {}).get("gold_draft", {}).get("skills", [])
    aligned: dict[str, str] = {}
    for surf in draft:
        hit = align_skill(surf, index, threshold=cut)
        if hit:
            aligned[hit["id"]] = surf
    gold, suspects = [], []
    for entry in row["skills"]:
        sid = entry["id"]
        traceable = sid in aligned or any(
            n.strip().casefold() in text.casefold() for n in _names(by_id, sid) if n
        )
        target = gold if traceable else suspects
        target.append({"id": sid, "name": _names(by_id, sid)[0] or sid})
    held = {e["id"] for e in row["skills"]}
    proposals = [
        {"skill_id": sid, "name": (by_id.get(sid) or {}).get("name") or sid, "span": surf}
        for sid, surf in aligned.items()
        if sid not in held
    ]
    return {
        "id": row["id"],
        "title": row.get("title") or row.get("id"),
        "text": text[:1500],
        "kept": gold,
        "suspects": suspects,
        "proposals": proposals,
        "unaligned": [s for s in draft if s not in set(aligned.values())],
    }


def next_row(file: str) -> dict:
    rows = read_jsonl(eval_dir() / FILES[file])
    done = sum(1 for r in rows if (r.get("notes") or {}).get("adjudicated"))
    out = {"file": file, "total": len(rows), "done": done, "row": None}
    row = next((r for r in rows if not (r.get("notes") or {}).get("adjudicated")), None)
    if row is None:
        return out
    if not (row.get("notes") or {}).get("gold_draft"):
        out["draft_missing"] = True
        return out
    index = _vocab()
    out["row"] = prep_row(row, index, {s["id"]: s for s in index}, load_freeze()["align_threshold"])
    return out


def apply_decision(payload: dict) -> dict:
    file = payload.get("file")
    if file not in FILES:
        raise ValueError(f"unknown file {file!r}")
    row_id = payload["row_id"]
    deleted = set(payload.get("deleted") or [])
    added = payload.get("added") or []
    path = eval_dir() / FILES[file]
    rows = read_jsonl(path)
    row = next((r for r in rows if r["id"] == row_id), None)
    if row is None:
        raise KeyError(row_id)
    if not payload.get("skip"):
        for item in added:
            if item.get("span"):
                row["mentions"] = (row.get("mentions") or []) + [
                    {"span": item["span"], "skill_id": item["skill_id"]}
                ]
        row["skills"] = [e for e in row["skills"] if e["id"] not in deleted] + [
            {"id": item["skill_id"], "kind": "required", "proficiency": None} for item in added
        ]
    _mark_done(row, skipped=bool(payload.get("skip")), deleted=sorted(deleted), added=[item["skill_id"] for item in added])
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    done = sum(1 for r in rows if (r.get("notes") or {}).get("adjudicated"))
    return {"file": file, "total": len(rows), "done": done}


def _ask(prompt: str, keys: str, default: str) -> str:
    try:
        raw = input(prompt).strip().lower()
    except EOFError:
        print()
        return "q"
    return raw if raw in keys else default


def _adjudicate_row(prep: dict) -> bool:
    print(f"\n[{prep['title']}] 原文（裁决只认这段）:")
    print(prep["text"])
    print(
        f"自动留 {len(prep['kept'])}（原文/草稿可溯）| 存疑 {len(prep['suspects'])}"
        f" | 提案加 {len(prep['proposals'])} | 草稿未对齐 {len(prep['unaligned'])}"
    )
    answer = _ask("回车=逐项 / A=全收提案 / D=全删存疑 / s=跳过 / q=保存退出: ", {"", "a", "d", "s", "q"}, "")
    if answer == "s":
        return "skip"
    if answer == "q":
        return False
    deleted: set[str] = set()
    added: list[dict] = []
    if answer == "d":
        deleted = {e["id"] for e in prep["suspects"]}
    elif answer == "a":
        added = list(prep["proposals"])
    else:
        for entry in prep["suspects"]:
            if _ask(f"  存疑 [{entry['name']}] 原文找不到 → d=删 / 回车=留: ", {"d", ""}, "") == "d":
                deleted.add(entry["id"])
        for item in prep["proposals"]:
            if _ask(f"  提案加 [{item['name']}]（草稿: {item['span']}）→ a=加 / 回车=不加: ", {"a", ""}, "") == "a":
                added.append(item)
    if deleted or added or answer in ("a", "d"):
        return {"deleted": sorted(deleted), "added": added}
    return "skip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="金标裁决工作台（ADR-0011）")
    parser.add_argument("--file", choices=("jd", "resume", "all"), default="all")
    args = parser.parse_args(argv)

    cut = load_freeze()["align_threshold"]
    index = _vocab()
    by_id = {s["id"]: s for s in index}
    chosen = FILES if args.file == "all" else {args.file: FILES[args.file]}

    for label, filename in chosen.items():
        path = eval_dir() / filename
        rows = read_jsonl(path)
        todo = [i for i, row in enumerate(rows) if not (row.get("notes") or {}).get("adjudicated")]
        if not todo:
            print(f"{filename}: 已全部裁决，跳过")
            continue
        shutil.copy2(path, path.with_suffix(".jsonl.bak"))
        try:
            for i, row in enumerate(rows):
                if i not in todo:
                    continue
                print(f"\n--- {filename} {i + 1}/{len(rows)} ---")
                outcome = _adjudicate_row(prep_row(row, index, by_id, cut))
                if outcome is False:
                    break
                if outcome == "skip":
                    continue
                row["mentions"] = (row.get("mentions") or []) + [
                    {"span": item["span"], "skill_id": item["skill_id"]}
                    for item in outcome["added"]
                    if item.get("span")
                ]
                row["skills"] = [e for e in row["skills"] if e["id"] not in set(outcome["deleted"])] + [
                    {"id": item["skill_id"], "kind": "required", "proficiency": None}
                    for item in outcome["added"]
                ]
                _mark_done(row, skipped=False, deleted=outcome["deleted"], added=[item["skill_id"] for item in outcome["added"]])
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{filename}: 已写回（备份 {path.with_suffix('.jsonl.bak').name}）")
    return 0
