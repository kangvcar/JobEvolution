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
            },
        },
    }
