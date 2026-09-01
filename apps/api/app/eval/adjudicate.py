"""ADR-0011 裁决工作台：人只对存疑项按键，工具写 jsonl。python -m app.eval adjudicate [--file jd|resume]"""

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


def _vocab() -> list[dict]:
    skills = json.loads((eval_dir() / "skills.json").read_text(encoding="utf-8"))
    vectors = embed([s["name"] for s in skills])
    for skill, vec in zip(skills, vectors, strict=True):
        skill["embedding"] = vec
    return skills


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


def _new_skill(name: str) -> dict:
    sid = "skill-" + hashlib.blake2b(name.strip().casefold().encode("utf-8"), digest_size=8).hexdigest()
    return {"id": sid, "name": name.strip(), "synonyms": [name.strip()], "embedding": None}


def _ask(prompt: str, keys: str, default: str) -> str:
    try:
        raw = input(prompt).strip().lower()
    except EOFError:
        print()
        return "q"
    return raw if raw in keys else default


def _adjudicate_row(row: dict, index: list[dict], by_id: dict, cut: float) -> bool:
    title = row.get("title") or row.get("id")
    text = _row_text(row)
    print(f"\n{'=' * 70}\n[{title}] 原文（裁决只认这段）:")
    print(text[:1500])
    draft = (row.get("notes") or {}).get("gold_draft", {}).get("skills", [])
    aligned = {}
    for surf in draft:
        hit = align_skill(surf, index, threshold=cut)
        if hit:
            aligned[hit["id"]] = surf

    gold = row["skills"]
    suspects, keeps = [], []
    for entry in gold:
        sid = entry["id"]
        if sid in aligned or any(n.strip().casefold() in text.casefold() for n in _names(by_id, sid) if n):
            keeps.append(entry)
        else:
            suspects.append(entry)
    adds = [(sid, surf) for sid, surf in aligned.items() if sid not in {e["id"] for e in gold}]

    print(f"自动留 {len(keeps)}（原文/草稿可溯）| 存疑 {len(suspects)} | 提案加 {len(adds)} | 草稿未对齐 {len(draft) - len(aligned)}")
    answer = _ask("回车=逐项 / A=全收提案 / D=全删存疑 / s=跳过 / q=保存退出: ", {"", "a", "d", "s", "q"}, "")
    if answer == "s":
        return True
    if answer == "q":
        return False

    deleted: set[str] = set()
    added: list[tuple[str, str]] = []
    if answer == "d":
        deleted = {e["id"] for e in suspects}
    if answer == "a":
        added = list(adds)
    if answer == "":
        for entry in suspects:
            names = " / ".join(n for n in _names(by_id, entry["id"]) if n)
            if _ask(f"  存疑 [{names}] 原文找不到 → d=删 / 回车=留: ", {"d", ""}, "") == "d":
                deleted.add(entry["id"])
        for sid, surf in adds:
            if _ask(f"  提案加 [{by_id[sid]['name']}]（草稿: {surf}）→ a=加 / 回车=不加: ", {"a", ""}, "") == "a":
                added.append((sid, surf))

    for sid, surf in added:
        row["mentions"] = (row.get("mentions") or []) + [{"span": surf, "skill_id": sid}]
    row["skills"] = [e for e in gold if e["id"] not in deleted] + [
        {"id": sid, "kind": "required", "proficiency": None} for sid, _ in added
    ]
    row.setdefault("notes", {})["adjudicated"] = {
        "date": date.today().isoformat(),
        "kept": len(keeps),
        "deleted": sorted(deleted),
        "added": [sid for sid, _ in added],
    }
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="金标裁决工作台（ADR-0011）")
    parser.add_argument("--file", choices=("jd", "resume", "all"), default="all")
    args = parser.parse_args(argv)

    all_files = {"jd": "jd.jsonl", "resume": "resume.jsonl"}
    names = all_files if args.file == "all" else {args.file: all_files[args.file]}
    cut = load_freeze()["align_threshold"]
    index = _vocab()
    by_id = {s["id"]: s for s in index}

    for label, filename in names.items():
        path = eval_dir() / filename
        rows = read_jsonl(path)
        todo = [i for i, row in enumerate(rows) if not (row.get("notes") or {}).get("adjudicated")]
        if not todo:
            print(f"{filename}: 已全部裁决，跳过")
            continue
        shutil.copy2(path, path.with_suffix(".jsonl.bak"))
        try:
            for i, row in enumerate(rows):
                if i in todo:
                    print(f"\n--- {filename} {i + 1}/{len(rows)} ---")
                    if not _adjudicate_row(row, index, by_id, cut):
                        break
        finally:
            with open(path, "w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{filename}: 已写回（备份 {path.with_suffix('.jsonl.bak').name}）")
    return 0
