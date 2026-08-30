from __future__ import annotations

import json
import sys
from app.eval.f1 import mean_f1, set_f1
from app.eval.freeze import align_threshold, freeze_hash, load_freeze
from app.eval.io import read_jsonl, write_json
from app.eval.paths import eval_dir, out_dir
from app.eval.scan import mention_skill_ids, skill_ids
from app.matching.score import compare_job

PASS = 0.90


def _index() -> list[dict]:
    path = eval_dir() / "skills.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    return rows


def _fail_if_low(name: str, summary: dict) -> None:
    write_json(out_dir() / f"{name}.json", summary)
    print(json.dumps({name: summary, "freeze": freeze_hash()[:12]}, ensure_ascii=False))
    if summary["f1"] < PASS:
        raise SystemExit(1)


def eval_jd(*, mock: bool = False) -> dict:
    # ponytail: pred is freeze-threshold vocab scan of stored text, not a second DeepSeek pass
    load_freeze()
    index = _index()
    cut = align_threshold()
    rows = []
    for item in read_jsonl(eval_dir() / "jd.jsonl"):
        gold = skill_ids(item.get("skills") or [])
        if mock:
            pred = set(gold)
        else:
            pred = skill_ids(mention_skill_ids(item.get("text") or "", index, threshold=cut))
        rows.append(set_f1(pred, gold))
    summary = {"task": "jd", "mock": mock, **mean_f1(rows)}
    _fail_if_low("jd", summary)
    return summary


def eval_resume(*, mock: bool = False) -> dict:
    load_freeze()
    index = _index()
    cut = align_threshold()
    rows = []
    for item in read_jsonl(eval_dir() / "resume.jsonl"):
        gold = skill_ids(item.get("skills") or [])
        if mock:
            pred = set(gold)
        else:
            pred = skill_ids(mention_skill_ids(item.get("text") or "", index, threshold=cut))
        rows.append(set_f1(pred, gold))
    summary = {"task": "resume", "mock": mock, **mean_f1(rows)}
    _fail_if_low("resume", summary)
    return summary


def eval_match(*, mock: bool = False) -> dict:
    load_freeze()
    rows = []
    for item in read_jsonl(eval_dir() / "match_pairs.jsonl"):
        gold = set(item.get("gap_ids") or [])
        if mock:
            pred = set(gold)
        else:
            report = compare_job(item.get("requires") or [], item.get("resume_skills") or [])
            pred = {row["skill_id"] for row in report["gaps"]}
        rows.append(set_f1(pred, gold))
    summary = {"task": "match", "mock": mock, **mean_f1(rows)}
    _fail_if_low("match", summary)
    return summary


def path_spotcheck() -> dict:
    """Learning path: shift-set skills should have an http(s) URL. Not an F1."""
    from app.matching.report import lookup_resource

    pairs = read_jsonl(eval_dir() / "match_pairs.jsonl")
    skills = []
    for item in pairs:
        report = compare_job(item.get("requires") or [], item.get("resume_skills") or [])
        for row in report.get("path") or []:
            skills.append(row)
            if len(skills) >= 20:
                break
        if len(skills) >= 20:
            break
    ok = 0
    for row in skills:
        url = lookup_resource(row.get("skill_id") or "", row.get("name") or "", complete_json=lambda *_: {})
        if str(url).startswith("http"):
            ok += 1
    return {"n": len(skills), "with_url": ok}


def write_summary(*, coverage: float | None, mock: bool) -> Path:
    from app.eval.freeze import freeze_hash as fh

    out = out_dir()
    jd = json.loads((out / "jd.json").read_text(encoding="utf-8"))
    resume = json.loads((out / "resume.json").read_text(encoding="utf-8"))
    match = json.loads((out / "match.json").read_text(encoding="utf-8"))
    path = path_spotcheck()
    cov = coverage if coverage is not None else None
    lines = [
        f"三项 F1  JD {jd['f1']:.3f}  简历 {resume['f1']:.3f}  匹配 {match['f1']:.3f}  n={jd['n']}/{resume['n']}/{match['n']}  mock={mock}",
        f"覆盖率  {cov:.1f}%" if cov is not None else "覆盖率  见 pytest --cov",
        f"学习路径抽检  {path['with_url']}/{path['n']} 条有可打开链接",
        f"freeze.json sha256  {fh()}",
        "",
    ]
    dest = out / "summary.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
