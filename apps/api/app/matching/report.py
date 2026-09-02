from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ipaddress
import re
import socket
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import quote, urlparse

from app.matching.bands import PATH_MAX
from app.matching.score import WATCHING_COPY, compare_job
from app.matching.session import cache_get, cache_set

NEIGHBOR = {
    "大模型应用工程师": "Agent 工程师",
    "Agent 工程师": "大模型应用工程师",
}

BAND_ORDER = {"不匹配": 0, "有明显差距": 1, "基本匹配": 2, "高度匹配": 3}

PRESET_URL = {
    "python": "https://docs.python.org/zh-cn/3/",
    "fastapi": "https://fastapi.tiangolo.com/",
    "neo4j": "https://neo4j.com/docs/",
    "rag": "https://python.langchain.com/docs/concepts/rag/",
}
RESOURCE_TTL = 24 * 3600
RESOURCE_PROMPT = (
    "Return JSON {url: https://...} with one official docs or open tutorial URL "
    "for this skill. No markdown."
)


def _preset_url(name: str) -> str | None:
    key = (name or "").casefold()
    for token, url in PRESET_URL.items():
        if token in key:
            return url
    return None


def _valid_url(value) -> str | None:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return text
    return None


def _verify_resource(url: str, skill: str) -> str | None:
    parsed = urlparse(url)
    try:
        host = parsed.hostname or ""
        for info in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(info[4][0])
            if address.is_private or address.is_loopback or address.is_link_local:
                return None
    except (ValueError, OSError):
        return None
    class LimitedRedirect(HTTPRedirectHandler):
        count = 0
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.count += 1
            if self.count > 3:
                raise OSError("too many redirects")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    try:
        response = build_opener(LimitedRedirect()).open(Request(url, headers={"User-Agent": "JobEvolution/1.0"}), timeout=5)
        final = _valid_url(response.geturl())
        body = response.read(1_000_001)
        if not final or len(body) > 1_000_000:
            return None
        title = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
        text = re.sub(r"\s+", " ", title.group(1).decode("utf-8", "ignore")) if title else ""
        return final if skill.casefold() in text.casefold() else None
    except (OSError, ValueError):
        return None


def lookup_resource(skill_id: str, name: str, complete_json=None) -> str:
    key = f"resource:{skill_id}" if skill_id else ""
    if key:
        cached = cache_get(key)
        if cached:
            return cached
    url = _preset_url(name)
    preset = url is not None
    if url is None:
        if complete_json is None:
            from app.llm.client import complete_json as complete_json
        try:
            payload = complete_json(
                [
                    {"role": "system", "content": RESOURCE_PROMPT},
                    {"role": "user", "content": name or skill_id},
                ],
            )
            url = _valid_url((payload or {}).get("url") if isinstance(payload, dict) else None)
        except Exception:
            url = None
    if not url:
        return ""
    if not preset:
        url = _verify_resource(url, name or skill_id) or ""
    if key:
        cache_set(key, url, RESOURCE_TTL)
    return url


def revalidate_resource(skill_id: str, name: str) -> bool:
    key = f"resource:{skill_id}" if skill_id else ""
    cached = cache_get(key) if key else None
    if not cached or _preset_url(name):
        return bool(cached)
    if _verify_resource(cached, name):
        cache_set(key, cached, RESOURCE_TTL)
        return True
    return False


def neighbor_name(job_name: str) -> str | None:
    return NEIGHBOR.get(job_name)


def recommend_jobs(jobs: list[dict], resume: dict, *, limit: int = 3) -> list[dict]:
    ranked = []
    resume_skills = resume.get("skills") or []
    for job in jobs:
        report = compare_job(job.get("requires") or [], resume_skills)
        covered = report.get("covered") or []
        specific = sum(1 for row in covered if row.get("required_proficiency") and row.get("skill_id"))
        evidence = sum(1 for row in covered if row.get("skill_id") in {f.get("skill_id") for f in resume.get("evidence_fragments") or []})
        reasons = [
            {"code": "band", "text": f"当前档位为{report['band']}"},
            {"code": "required", "text": f"必备覆盖 {report['req_cover']:g}/{report['req_full']:g}"},
        ]
        ranked.append(
            (
                BAND_ORDER.get(report["band"], 0),
                report.get("req_cover", 0) / report.get("req_full", 1) if report.get("req_full") else 0,
                evidence,
                specific,
                -len(report.get("shift_ids") or []),
                len(job.get("sources") or []),
                job,
                report,
                reasons,
            )
        )
    ranked.sort(key=lambda row: row[:6], reverse=True)
    return [
        {
            "job_id": row[6]["id"],
            "name": row[6].get("name") or row[6]["id"],
            "status": row[6].get("status"),
            "band": row[7]["band"],
            "reasons": row[8],
        }
        for row in ranked[: max(0, limit)]
    ]


def direction_report(jobs: list[dict], resume: dict) -> dict:
    results = []
    for job in jobs[:2]:
        core = compare_job(job.get("requires") or [], resume.get("skills") or [])
        evidence_ids = {row.get("skill_id") for row in resume.get("evidence_fragments") or []}
        results.append(
            {
                "job_id": job["id"],
                "name": job.get("name") or job["id"],
                "band": core["band"],
                "required_coverage": {"covered": core["req_cover"], "total": core["req_full"]},
                "resume_evidence": sum(1 for row in core.get("covered") or [] if row.get("skill_id") in evidence_ids),
                "transferable_engineering": sum(1 for row in core.get("covered") or [] if row.get("category") == "engineering"),
                "job_specific_experience": sum(1 for row in core.get("covered") or [] if row.get("category") == "domain"),
                "experience_education_risk": bool(resume.get("experience") == "简历未标" or resume.get("education") == "简历未标"),
                "shift_set": core.get("path") or [],
            }
        )
    if len(results) < 2:
        return {"direction": "insufficient", "jobs": results}
    keys = ("band", "required_coverage", "resume_evidence", "transferable_engineering", "job_specific_experience", "experience_education_risk")
    direction = "无法区分方向" if all(results[0][key] == results[1][key] for key in keys) else ""
    if not direction:
        left = (BAND_ORDER.get(results[0]["band"], 0), results[0]["required_coverage"]["covered"], results[0]["resume_evidence"])
        right = (BAND_ORDER.get(results[1]["band"], 0), results[1]["required_coverage"]["covered"], results[1]["resume_evidence"])
        direction = results[0]["name"] if left > right else results[1]["name"]
    return {"direction": direction, "jobs": results}


def evidence_map(requires: list[dict], resume: dict) -> list[dict]:
    fragments = {row.get("skill_id"): row for row in resume.get("evidence_fragments") or [] if row.get("skill_id")}
    return [
        {
            "requirement_id": row.get("skill_id"),
            "requirement_name": row.get("name") or row.get("skill_id"),
            "evidence_fragment_id": (fragments.get(row.get("skill_id")) or {}).get("id"),
            "evidence_level": (fragments.get(row.get("skill_id")) or {}).get("evidence_level") or "未提及",
            "quote": (fragments.get(row.get("skill_id")) or {}).get("text") or "",
        }
        for row in requires
    ]


def simulate_job(requires: list[dict], resume: dict, assumed_skill_ids: list[str]) -> dict:
    original = compare_job(requires, resume.get("skills") or [])
    by_id = {row.get("skill_id"): row for row in resume.get("skills") or []}
    assumed = [sid for sid in dict.fromkeys(assumed_skill_ids) if sid not in by_id]
    simulated_skills = [*(resume.get("skills") or []), *({"skill_id": sid, "name": sid, "proficiency": "able"} for sid in assumed)]
    simulated = compare_job(requires, simulated_skills)
    return {
        "original_band": original["band"],
        "simulated_band": simulated["band"],
        "original_score": original["score"],
        "simulated_score": simulated["score"],
        "shift_set": simulated.get("path") or [],
        "allowed_skill_ids": list(original.get("shift_ids") or []),
        "assumed_skill_ids": assumed,
    }


def migration_map(jobs: list[dict], resume: dict) -> list[dict]:
    result = []
    for job in jobs[:3]:
        requires = job.get("requires") or []
        report = compare_job(requires, resume.get("skills") or [])
        target_ids = {row.get("skill_id") for row in requires}
        resume_ids = {row.get("skill_id") for row in resume.get("skills") or []}
        result.append(
            {
                "job_id": job.get("id"),
                "name": job.get("name") or job.get("id"),
                "band": report["band"],
                "minimum_shift_skill_count": len(report.get("shift_ids") or []),
                "shared_capabilities": sorted(target_ids & resume_ids),
                "unique_requirements": sorted(target_ids - resume_ids),
            }
        )
    return result


def market_signal_radar(watching: list[dict], jobs: list[dict], target_job_id: str) -> list[dict]:
    total_jobs = len(jobs)
    rows = []
    for signal in watching:
        sid = signal.get("skill_id")
        matches = [job for job in jobs if sid in {row.get("skill_id") for row in job.get("requires") or []}]
        evidence = [source for job in matches for source in job.get("sources") or []]
        rows.append(
            {
                "skill_id": sid,
                "name": signal.get("name") or sid,
                "sample_occurrence_ratio": round(len(matches) / total_jobs, 4) if total_jobs else 0,
                "company_count": len(set(evidence)),
                "period_change": signal.get("period_change") or "观测中",
                "evidence_summary": f"{len(matches)} 个公开岗位提及，覆盖 {len(set(evidence))} 家招聘公司",
                "formal_requirement_reason": "观测样本尚未达到必备多数票和独立来源门槛",
            }
        )
    return rows


def resume_analysis(*, job: dict, requires: list[dict], resume: dict, core: dict | None = None) -> dict:
    core = core or compare_job(requires, resume.get("skills") or [])
    fragments = resume.get("evidence_fragments") or []
    evidence_by_skill = {row.get("skill_id"): row for row in fragments if row.get("skill_id")}
    strengths = []
    for row in core.get("covered") or []:
        fragment = evidence_by_skill.get(row.get("skill_id"))
        if fragment:
            strengths.append({"text": f"有{row.get('name') or row.get('skill_id')}的简历证据", "evidence_fragment_id": fragment.get("id") or fragment.get("skill_id"), "quote": fragment.get("text")})
        if len(strengths) == 3:
            break
    risks = [
        {"text": f"缺少{row.get('name') or row.get('skill_id')}的可核对证据", "check_scope": "经历、项目和技能栏", "requirement_id": row.get("skill_id")}
        for row in (core.get("gaps") or [])[:3]
    ]
    states = []
    for row in requires:
        fragment = evidence_by_skill.get(row.get("skill_id"))
        states.append({"skill_id": row.get("skill_id"), "name": row.get("name"), "state": "证据充分" if fragment and fragment.get("evidence_level") == "result" else "已提及但证据较弱" if fragment else "简历中未找到", "evidence_fragment_id": fragment.get("id") if fragment else None, "quote": fragment.get("text") if fragment else "", "check_scope": "经历、项目和技能栏" if not fragment else "引用的简历原文"})
    rewrites = []
    for fragment in fragments:
        rewrites.append({"original": fragment.get("text"), "problem": "缺少职责或可核对结果" if fragment.get("evidence_level") != "result" else "可保留并补充上下文", "suggestion": fragment.get("text"), "facts_used": [fragment.get("text")], "facts_to_add": ["规模、延迟、成本或业务结果中的一项"] if fragment.get("evidence_level") != "result" else []})
    capability = [{"skill_id": row.get("skill_id"), "name": row.get("name"), "why": "补齐下一档必备缺口"} for row in (core.get("gaps") or [])[:3]]
    job_name = job.get("name") or "目标岗位"
    strength_text = "、".join(item.get("quote") or "已有项目经历" for item in strengths[:2]) or "当前简历证据仍需补充"
    band = core.get("band") or "不匹配"
    return {
        "one_sentence": f"你目前处于{band}，简历已呈现部分{job_name}相关能力，但还缺少可核对的关键证据。",
        "core_judgments": {
            "fit_band": band,
            "advantage": strengths[0]["text"] if strengths else "尚未找到可引用的优势证据",
            "blocker": risks[0]["text"] if risks else "暂无明确阻碍",
        },
        "positioning": {"text": f"当前简历更接近{job_name}，主要阻碍是可核对证据不足。", "evidence_fragment_ids": [item.get("evidence_fragment_id") for item in strengths], "check_scope": "简历全文与当前可诊断岗位集合"},
        "strengths": strengths,
        "risks": risks,
        "content_states": states,
        "evidence_map": states,
        "keywords": {
            "已有证据": [item["name"] for item in states if item["state"] == "证据充分"],
            "只有提及": [item["name"] for item in states if item["state"] == "已提及但证据较弱"],
            "简历未找到证据": [item["name"] for item in states if item["state"] == "简历中未找到"],
        },
        "rewrites": rewrites,
        "project_evidence_prompts": [
            {"project": project.get("name") or "项目", "dimensions": ["数据规模", "延迟", "评测结果"][:2]}
            for project in (resume.get("projects") or [])
        ] or [
            {"evidence_fragment_id": fragment.get("id") or fragment.get("skill_id"), "dimensions": ["数据规模", "延迟"]}
            for fragment in fragments if fragment.get("section") == "project"
        ][:2],
        "actions": {"rewrite": rewrites[:5], "capability": capability},
        "narrative": f"我有{strength_text}的实践基础，正在申请{job_name}。下一步会补充可核对的项目结果，说明自己承担的职责、规模和影响。",
    }


def attach_urls(path: list[dict]) -> list[dict]:
    if not path:
        return []

    def one(step: dict) -> dict:
        item = dict(step)
        item["url"] = step.get("url") or lookup_resource(
            step.get("skill_id") or "",
            step.get("name") or "",
        )
        return item

    with ThreadPoolExecutor(max_workers=min(5, len(path))) as pool:
        return list(pool.map(one, path))


def wrap_report(
    *,
    job: dict,
    requires: list[dict],
    resume: dict,
    neighbor: dict | None,
    watching: list[dict],
    slice_data: dict | None = None,
) -> dict:
    core = compare_job(requires, resume.get("skills") or [])
    core["path"] = attach_urls(core["path"])
    analysis = resume_analysis(job=job, requires=requires, resume=resume, core=core)
    summary = (
        f"对照{job.get('name') or '目标岗'}，档位「{core['band']}」。"
        f"必备覆盖 {core['req_cover']:g}/{core['req_full']:g}。"
    )
    names = {row["skill_id"]: row.get("name") or row["skill_id"] for row in requires}
    neighbors = [
        {"job_id": job["id"], "name": job.get("name") or job["id"], "band": core["band"]}
    ]
    if neighbor:
        nrep = compare_job(neighbor["requires"], resume.get("skills") or [])
        neighbors.append(
            {
                "job_id": neighbor["job"]["id"],
                "name": neighbor["job"]["name"],
                "band": nrep["band"],
            }
        )
    return {
        "job_id": job["id"],
        "session_id": resume.get("session_id"),
        "graph_release": resume.get("graph_release"),
        "metadata": {
            "graph_release": resume.get("graph_release"),
            "evidence_count": len({source for row in requires for source in row.get("sources") or []}),
            "f1": {"jd": 0.749, "resume": 0.993, "match": 1.0},
            "formula": "required coverage + 0.3 × bonus coverage; experience/education excluded",
        },
        "preview_text": resume.get("preview_text") or "",
        "score": core["score"],
        "band": core["band"],
        "gaps": core["gaps"],
        "groups": {
            "judge": {
                "summary": summary,
                "band": core["band"],
                "cells": {
                    "required": f"{core['req_cover']:g}/{core['req_full']:g}",
                    "half": str(len(core["half"])),
                    "experience": resume.get("experience") or "简历未标",
                    "education": resume.get("education") or "简历未标",
                },
                "job_status": {"emerging": "萌芽", "formed": "成型"}.get(
                    job.get("status") or "", job.get("status")
                ),
                "shift_set": [
                    {"skill_id": sid, "name": names.get(sid, sid)}
                    for sid in core["shift_ids"][:PATH_MAX]
                ],
            },
            "locate": {
                "neighbors": neighbors,
                "hits": [
                    {"skill_id": row["skill_id"], "name": row["name"], "cover": row.get("cover")}
                    for row in core["covered"]
                ],
                "slice": slice_data or {"categories": [], "requires": [], "period_delta": {}},
            },
            "act": {"path": core["path"], "ledger": core["ledger"]},
            "explain": {
                "watching_copy": WATCHING_COPY,
                "watching": watching,
                "half": core["half"],
                "extra": core["extra"],
                "covered": core["covered"],
                "notes": "半档记 0.5；加分权重 0.3。匹配分只在载荷里，页面不渲染成 0–100。",
                "analysis": analysis,
            },
        },
    }
