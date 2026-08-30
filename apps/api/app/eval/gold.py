from __future__ import annotations

import json
from pathlib import Path

from app.eval.io import write_json, write_jsonl
from app.eval.paths import eval_dir, repo_root
from app.eval.scan import duty_text, mention_skill_ids
from app.matching.score import compare_job
from app.pipeline.__main__ import match_target
from app.pipeline.status import job_id_for

DOMAIN_QUOTA = {"ai": 40, "data": 12, "system": 12, "iot": 12}
PAIR_TARGET = 100
RESUME_N = 100
JD_N = 100
CONTEST = ("Agent 工程师", "大模型应用工程师")


def _load_doc(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    root = repo_root()
    try:
        doc["path"] = str(path.relative_to(root))
    except ValueError:
        doc["path"] = str(path)
    return doc


def _pick_jd() -> list[dict]:
    files = sorted((repo_root() / "data" / "jd").glob("jd-*.json"))
    picked: list[dict] = []
    seen: set[str] = set()
    named = {name: 0 for name in CONTEST}
    domains = {key: 0 for key in DOMAIN_QUOTA}

    def take(doc: dict) -> bool:
        sid = doc.get("id") or doc.get("path")
        if not sid or sid in seen:
            return False
        seen.add(sid)
        picked.append(doc)
        name = match_target(doc.get("title") or "")
        if name in named:
            named[name] += 1
        domains[doc.get("domain") or "ai"] = domains.get(doc.get("domain") or "ai", 0) + 1
        return True

    def need_named(doc: dict) -> bool:
        name = match_target(doc.get("title") or "")
        return bool(name in named and named[name] < 8)

    def need_domain(doc: dict) -> bool:
        domain = doc.get("domain") or "ai"
        return domains.get(domain, 0) < DOMAIN_QUOTA.get(domain, 0)

    for path in files:
        if all(v >= 8 for v in named.values()):
            break
        doc = _load_doc(path)
        if doc and need_named(doc):
            take(doc)
    for path in files:
        if all(domains.get(k, 0) >= n for k, n in DOMAIN_QUOTA.items()):
            break
        doc = _load_doc(path)
        if doc and need_domain(doc):
            take(doc)
    for path in files:
        if len(picked) >= JD_N:
            break
        doc = _load_doc(path)
        if doc:
            take(doc)
    return picked


def build_gold(*, index: list[dict], jobs: list[dict]) -> None:
    dest = eval_dir()
    dest.mkdir(parents=True, exist_ok=True)
    write_json(
        dest / "skills.json",
        [{"id": s["id"], "name": s.get("name") or "", "synonyms": list(s.get("synonyms") or [])} for s in index],
    )
    jd_rows = []
    for i, doc in enumerate(_pick_jd(), start=1):
        text = duty_text(doc.get("body") or "")[:2500]
        skills = mention_skill_ids(text, index)
        name = match_target(doc.get("title") or "")
        jd_rows.append(
            {
                "id": f"jd-{i:04d}",
                "source": doc.get("source") or "local",
                "company": doc.get("company") or "",
                "title": doc.get("title") or "",
                "path": doc.get("path") or "",
                "domain": doc.get("domain") or "ai",
                "job_id": job_id_for(name) if name else None,
                "job_name": name,
                "skills": skills,
                "mentions": [{"span": s.get("name") or "", "skill_id": s["id"]} for s in skills],
                "watching": [],
                "text": text,
            }
        )
    write_jsonl(dest / "jd.jsonl", jd_rows)

    vocab = [s for s in index if s.get("name")]
    resume_rows = []
    for i in range(RESUME_N):
        chunk = vocab[i % max(len(vocab), 1) : i % max(len(vocab), 1) + 8]
        if len(chunk) < 4:
            chunk = vocab[:8]
        names = [s["name"] for s in chunk if s.get("name")]
        mark = i % 3 == 0
        head = "熟练掌握 " if mark else "技能 "
        text = (
            f"姓名 评测{i:03d}\n"
            f"{head}{'、'.join(names)}\n"
            f"项目：用 {' / '.join(names[:3])} 做检索与接口。\n"
        )
        skills = [{"id": s["id"], "proficiency": "able" if mark else None} for s in chunk]
        resume_rows.append(
            {
                "id": f"cv-{i:04d}",
                "layout": "split" if i % 7 == 0 else "single",
                "kind": "fresh" if i % 5 == 0 else "social",
                "text": text,
                "skills": skills,
                "education": "本科",
                "experience": "2年",
            }
        )
    write_jsonl(dest / "resume.jsonl", resume_rows)

    requires_by_job = []
    for job in jobs:
        req = job.get("requires") or []
        if not req:
            continue
        requires_by_job.append((job, req))
    if not requires_by_job:
        fake = [
            {"skill_id": vocab[0]["id"], "name": vocab[0]["name"], "kind": "required", "proficiency": "able"}
        ]
        requires_by_job = [({"id": "job-eval", "name": "评测岗"}, fake)]
    pairs = []
    n = 0
    while n < PAIR_TARGET:
        job, req = requires_by_job[n % len(requires_by_job)]
        cv = resume_rows[n % len(resume_rows)]
        resume_skills = [
            {"skill_id": s["id"], "name": s["id"], "proficiency": s.get("proficiency")}
            for s in cv["skills"]
        ]
        report = compare_job(req, resume_skills)
        pairs.append(
            {
                "id": f"pair-{n:04d}",
                "resume_id": cv["id"],
                "job_id": job["id"],
                "job_name": job.get("name") or "",
                "resume_skills": resume_skills,
                "requires": [
                    {
                        "skill_id": r["skill_id"],
                        "name": r.get("name") or r["skill_id"],
                        "kind": r.get("kind") or "required",
                        "proficiency": r.get("proficiency") or "able",
                    }
                    for r in req
                ],
                "gap_ids": [g["skill_id"] for g in report["gaps"]],
            }
        )
        n += 1
    write_jsonl(dest / "match_pairs.jsonl", pairs)


def main() -> int:
    from app import graph

    if graph._driver is None:
        graph.init_graph()
    index = graph.list_skills(with_embed=False)
    jobs = []
    for row in graph.list_jobs(domain=None, status=None, q=None):
        jobs.append({**row, "requires": graph.list_requires(row["id"])})
    build_gold(index=index, jobs=jobs)
    dest = eval_dir()
    print(
        json.dumps(
            {
                "jd": sum(1 for _ in (dest / "jd.jsonl").open(encoding="utf-8")),
                "resume": sum(1 for _ in (dest / "resume.jsonl").open(encoding="utf-8")),
                "match": sum(1 for _ in (dest / "match_pairs.jsonl").open(encoding="utf-8")),
                "skills": len(index),
            },
            ensure_ascii=False,
        )
    )
    return 0
