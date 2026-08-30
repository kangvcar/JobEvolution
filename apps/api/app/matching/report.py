from __future__ import annotations

from urllib.parse import quote

from app.matching.bands import PATH_MAX
from app.matching.score import WATCHING_COPY, compare_job

NEIGHBOR = {
    "大模型应用工程师": "Agent 工程师",
    "Agent 工程师": "大模型应用工程师",
}

PRESET_URL = {
    "python": "https://docs.python.org/zh-cn/3/",
    "fastapi": "https://fastapi.tiangolo.com/",
    "neo4j": "https://neo4j.com/docs/",
    "rag": "https://python.langchain.com/docs/concepts/rag/",
}


def resource_url(name: str) -> str:
    key = (name or "").casefold()
    for token, url in PRESET_URL.items():
        if token in key:
            return url
    return "https://www.bing.com/search?q=" + quote(name or "skill")


def neighbor_name(job_name: str) -> str | None:
    return NEIGHBOR.get(job_name)


def attach_urls(path: list[dict]) -> list[dict]:
    out = []
    for step in path:
        item = dict(step)
        item["url"] = step.get("url") or resource_url(step.get("name") or "")
        out.append(item)
    return out


def wrap_report(
    *,
    job: dict,
    requires: list[dict],
    resume: dict,
    neighbor: dict | None,
    watching: list[dict],
) -> dict:
    core = compare_job(requires, resume.get("skills") or [])
    core["path"] = attach_urls(core["path"])
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
            },
            "act": {"path": core["path"], "ledger": core["ledger"]},
            "explain": {
                "watching_copy": WATCHING_COPY,
                "watching": watching,
                "half": core["half"],
                "extra": core["extra"],
                "covered": core["covered"],
                "notes": "半档记 0.5；加分权重 0.3。匹配分只在载荷里，页面不渲染成 0–100。",
            },
        },
    }
