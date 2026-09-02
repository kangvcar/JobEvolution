from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.eval.f1 import mean_f1, set_f1
from app.eval.freeze import align_threshold, freeze_hash, load_freeze
from app.eval.io import read_jsonl, write_json
from app.eval.paths import eval_dir, out_dir
from app.eval.scan import mention_skill_ids, skill_ids
from app.matching.resume import parse_resume
from app.matching.score import compare_job
from app.pipeline.align import align_skill, split_composite
from app.pipeline.extract import augment_extracted_skills, parse_extracted

PASS = 0.90
# DeepSeek occasionally truncates concurrent long JSON responses; two workers
# keep the frozen evaluation reproducible without changing production throughput.
JD_WORKERS = 2
RESUME_WORKERS = 4


def _index() -> list[dict]:
    rows = json.loads((eval_dir() / "skills.json").read_text(encoding="utf-8"))
    # 索引必须带嵌入：align_skill 的余弦分支对无 embedding 的词条直接跳过，
    # 缺了它评测对齐退化成纯精确匹配，与生产口径（冻结阈值余弦）不符
    from app.llm.embed import embed

    vectors = embed([row["name"] for row in rows])
    for row, vec in zip(rows, vectors, strict=True):
        row["embedding"] = vec
    return rows


def _write_result(name: str, summary: dict) -> None:
    write_json(out_dir() / f"{name}.json", summary)
    print(json.dumps({name: summary, "freeze": freeze_hash()[:12]}, ensure_ascii=False))


def _evaluate(name: str, items: list[dict], predict, *, mock: bool, workers: int) -> dict:
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(predict, item) for item in items]
        for future in as_completed(futures):
            rows.append(future.result())
            # ponytail: 逐条落盘只为中断续跑看进度；全量完成后以最终 _write_result 为准
            write_json(out_dir() / f"{name}.json", {"task": name, "mock": mock, **mean_f1(rows)})
    summary = {"task": name, "mock": mock, **mean_f1(rows)}
    _write_result(name, summary)
    return summary


def eval_jd(*, mock: bool = False) -> dict:
    load_freeze()
    index = _index()
    cut = align_threshold()
    from app.llm.client import complete_json

    def predict(item: dict) -> dict:
        gold = skill_ids(item.get("skills") or [])
        if mock:
            pred = set(gold)
        else:
            snapshot = {
                "title": item.get("title") or item.get("job_name") or "",
                "domain": item.get("domain") or "",
                "body": item.get("text") or "",
            }
            parsed = parse_extracted(complete_json, snapshot=snapshot)
            parsed = augment_extracted_skills(parsed, snapshot["body"], index, threshold=cut)
            pred = set()
            # 只允许回指 JD 原文的词表命中，阻止语义嵌入把模型臆测变成技能事实。
            mentioned_ids = {row["id"] for row in mention_skill_ids(snapshot["body"], index, threshold=cut)}
            for skill in parsed.skills:
                if skill.section not in ("duty", "requirement"):
                    continue
                for surface in split_composite(skill.name, index):
                    hit = align_skill(surface, index, threshold=cut)
                    if hit and hit["id"] in mentioned_ids:
                        pred.add(hit["id"])
        return set_f1(pred, gold)

    return _evaluate("jd", read_jsonl(eval_dir() / "jd.jsonl"), predict, mock=mock, workers=JD_WORKERS)


def eval_resume(*, mock: bool = False) -> dict:
    load_freeze()
    index = _index()
    def predict(item: dict) -> dict:
        gold = skill_ids(item.get("skills") or [])
        if mock:
            pred = set(gold)
        else:
            parsed = parse_resume(item.get("text") or "", index, threshold=align_threshold(), strict=True)
            pred = {row["skill_id"] for row in parsed.get("skills") or [] if row.get("skill_id")}
        return set_f1(pred, gold)

    return _evaluate("resume", read_jsonl(eval_dir() / "resume.jsonl"), predict, mock=mock, workers=RESUME_WORKERS)


def eval_match(*, mock: bool = False) -> dict:
    load_freeze()
    def predict(item: dict) -> dict:
        gold = set(item.get("gap_ids") or [])
        if mock:
            pred = set(gold)
        else:
            report = compare_job(item.get("requires") or [], item.get("resume_skills") or [])
            pred = {row["skill_id"] for row in report["gaps"]}
        return set_f1(pred, gold)

    return _evaluate("match", read_jsonl(eval_dir() / "match_pairs.jsonl"), predict, mock=mock, workers=JD_WORKERS)


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


def write_summary(
    *,
    coverage: float | None,
    mock: bool,
    results: dict[str, dict] | None = None,
    errors: dict[str, str] | None = None,
    lows: dict[str, str] | None = None,
) -> Path:
    from app.eval.freeze import freeze_hash as fh

    out = out_dir()
    if results is None:
        results = {
            name: json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("jd", "resume", "match")
        }
    errors = errors or {}
    lows = lows or {}

    def metric(name: str) -> str:
        row = results.get(name)
        if row and bool(row.get("mock")) != mock:
            return "未得真数"
        return f"{row['f1']:.3f}" if row else "未得真数"

    def size(name: str) -> str:
        row = results.get(name)
        return str(row.get("n") or 0) if row else "0"

    path = path_spotcheck()
    cov = coverage if coverage is not None else None
    lines = [
        f"三项 F1  JD {metric('jd')}  简历 {metric('resume')}  匹配 {metric('match')}  n={size('jd')}/{size('resume')}/{size('match')}  mock={mock}",
        f"覆盖率  {cov:.1f}%" if cov is not None else "覆盖率  见 pytest --cov",
        f"学习路径抽检  {path['with_url']}/{path['n']} 条有可打开链接",
        f"freeze.json sha256  {fh()}",
    ]
    for name in ("jd", "resume", "match"):
        if name in lows:
            lines.append(f"{name.upper()} 低于线  {lows[name]}")
        elif name in errors:
            lines.append(f"{name.upper()} 未得真数  {errors[name]}")
    if "jd" in lows:
        try:
            sample_ids = [row.get("id") for row in read_jsonl(eval_dir() / "jd.jsonl")[:3] if row.get("id")]
        except (OSError, ValueError):
            sample_ids = []
        lines.append(f"JD 差距样本  {'、'.join(sample_ids) or '评测集不可读'}")
        lines.append("JD 下一修复方向 先用冻结词表做候选召回，再让模型判断职责/要求和必备/加分，最后处理别名与复合技能对齐。")
    lines.append("")
    dest = out / "summary.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
