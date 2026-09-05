from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ipaddress
import re
import socket
import ssl
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import quote, urlparse, urljoin

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
    try:
        for _ in range(4):
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return None
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if port not in {80, 443}:
                return None
            addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
                return None
            connection = (HTTPSConnection if parsed.scheme == "https" else HTTPConnection)(parsed.hostname, port, timeout=5)
            try:
                # 连接已校验的 IP；TLS 仍验证原域名，避免二次 DNS 解析和重定向访问内网。
                connection.sock = socket.create_connection((addresses[0][4][0], port), timeout=5)
                if parsed.scheme == "https":
                    connection.sock = ssl.create_default_context().wrap_socket(connection.sock, server_hostname=parsed.hostname)
                connection.request("GET", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), headers={"User-Agent": "JobEvolution/1.0"})
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        return None
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    return None
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    return None
                title = re.search(rb"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                text = re.sub(r"\s+", " ", title.group(1).decode("utf-8", "ignore")) if title else ""
                return url if skill.casefold() in text.casefold() else None
            finally:
                connection.close()
    except (OSError, ValueError):
        return None
    return None


def lookup_resource(skill_id: str, name: str, complete_json=None) -> str:
    key = f"resource:v2:{skill_id}" if skill_id else ""
    if key:
        cached = cache_get(key)
        if cached:
            return cached
    url = _preset_url(name)
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
    url = _verify_resource(url, name or skill_id) or ""
    if key and url:
        cache_set(key, url, RESOURCE_TTL)
    return url


def revalidate_resource(skill_id: str, name: str) -> bool:
    key = f"resource:v2:{skill_id}" if skill_id else ""
    cached = cache_get(key) if key else None
    if not cached:
        return False
    if _verify_resource(cached, name):
        cache_set(key, cached, RESOURCE_TTL)
        return True
    return False


def neighbor_name(job_name: str) -> str | None:
    return NEIGHBOR.get(job_name)


def recommend_jobs(jobs: list[dict], resume: dict, *, limit: int = 3) -> list[dict]:
    ranked = []
    resume_skills = resume.get("skills") or []
    evidence_ids = {f.get("skill_id") for f in resume.get("evidence_fragments") or []}
    for job in jobs:
        report = compare_job(job.get("requires") or [], resume_skills)
        covered = report.get("covered") or []
        specific_evidence = sum(1 for row in covered if row.get("category") == "domain" and row.get("skill_id") in evidence_ids)
        transferable = sum(1 for row in covered if row.get("category") == "engineering")
        reasons = [
            {"code": "band", "text": f"当前档位为{report['band']}"},
            {"code": "required", "text": f"必备覆盖 {report['req_cover']:g}/{report['req_full']:g}"},
        ]
        ranked.append(
            (
                BAND_ORDER.get(report["band"], 0),
                report.get("req_cover", 0) / report.get("req_full", 1) if report.get("req_full") else 0,
                specific_evidence,
                transferable,
                str(job.get("latest_observed_at") or job.get("updated_at") or ""),
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


def _direction_explanation(direction: str, left: dict, right: dict) -> str:
    if direction == "无法区分方向":
        return (
            f"{left['name']}与{right['name']}的档位、必备覆盖、岗位专属证据、可迁移工程能力和最小换档项目前完全相同。"
            "现有简历证据还不足以判断更接近哪一个，请比较各自换档条件后再选。"
        )
    winner, other = (left, right) if direction == left["name"] else (right, left)
    reasons = []
    if winner["band"] != other["band"]:
        reasons.append(f"档位是{winner['band']}，对照岗是{other['band']}")
    if winner["required_coverage"] != other["required_coverage"]:
        reasons.append(
            f"必备覆盖 {winner['required_coverage']['covered']:g}/{winner['required_coverage']['total']:g}，"
            f"对照岗 {other['required_coverage']['covered']:g}/{other['required_coverage']['total']:g}"
        )
    if winner["job_specific_evidence"] != other["job_specific_evidence"]:
        reasons.append(f"岗位专属证据 {winner['job_specific_evidence']} 项，对照岗 {other['job_specific_evidence']} 项")
    if winner["minimum_shift_skill_count"] != other["minimum_shift_skill_count"]:
        reasons.append(f"最小换档 {winner['minimum_shift_skill_count']} 项，对照岗 {other['minimum_shift_skill_count']} 项")
    detail = "；".join(reasons) or "分项比较后综合领先"
    return f"当前更接近{winner['name']}。{detail}。"


def direction_report(jobs: list[dict], resume: dict) -> dict:
    results = []
    for job in jobs[:2]:
        core = compare_job(job.get("requires") or [], resume.get("skills") or [])
        evidence_ids = {row.get("skill_id") for row in resume.get("evidence_fragments") or []}
        covered_names = [row.get("name") or row.get("skill_id") for row in (core.get("covered") or [])[:6]]
        gap_names = [row.get("name") or row.get("skill_id") for row in (core.get("gaps") or [])[:6]]
        results.append(
            {
                "job_id": job["id"],
                "name": job.get("name") or job["id"],
                "band": core["band"],
                "required_coverage": {"covered": core["req_cover"], "total": core["req_full"]},
                "resume_evidence": sum(1 for row in core.get("covered") or [] if row.get("skill_id") in evidence_ids),
                "transferable_engineering": sum(1 for row in core.get("covered") or [] if row.get("category") == "engineering"),
                "job_specific_experience": sum(1 for row in core.get("covered") or [] if row.get("category") == "domain"),
                "job_specific_evidence": sum(1 for row in core.get("covered") or [] if row.get("category") == "domain" and row.get("skill_id") in evidence_ids),
                "experience_education_risk": bool(resume.get("experience") == "简历未标" or resume.get("education") == "简历未标"),
                "shift_set": core.get("path") or [],
                "minimum_shift_skill_count": len(core.get("shift_ids") or []),
                "covered_names": covered_names,
                "gap_names": gap_names,
                "summary": (
                    f"{job.get('name') or job['id']}当前档位{core['band']}，"
                    f"必备覆盖 {core['req_cover']:g}/{core['req_full']:g}，"
                    f"换档还差 {len(core.get('shift_ids') or [])} 项。"
                ),
            }
        )
    if len(results) < 2:
        return {"direction": "insufficient", "jobs": results, "explanation": ""}
    def direction_key(row):
        coverage = row["required_coverage"]
        return (BAND_ORDER.get(row["band"], 0), coverage["covered"] / coverage["total"] if coverage["total"] else 0,
                row["job_specific_evidence"], row["transferable_engineering"], -row["minimum_shift_skill_count"])
    left, right = map(direction_key, results)
    direction = "无法区分方向" if left == right else ""
    if not direction:
        direction = results[0]["name"] if left > right else results[1]["name"]
    added = [row.get("name") or row.get("skill_id") for row in resume.get("user_added") or []]
    note = f" 你补充的技能（简历尚未证明，不计入匹配）：{'、'.join(added)}。" if added else ""
    return {"direction": direction, "jobs": results, "explanation": _direction_explanation(direction, results[0], results[1]) + note}


def evidence_map(requires: list[dict], resume: dict) -> list[dict]:
    fragments: dict[str, list[dict]] = {}
    for fragment in resume.get("evidence_fragments") or []:
        if fragment.get("skill_id"):
            fragments.setdefault(str(fragment["skill_id"]), []).append(fragment)
    relations = []
    for row in requires:
        matches = fragments.get(str(row.get("skill_id")), [])
        if not matches:
            matches = [{}]
        relations.extend(
            {
                "requirement_id": row.get("skill_id"),
                "requirement_name": row.get("name") or row.get("skill_id"),
                "evidence_fragment_id": fragment.get("id"),
                "evidence_level": fragment.get("evidence_level") or "未提及",
                "quote": fragment.get("text") or "",
            }
            for fragment in matches
        )
    return relations


def simulate_job(requires: list[dict], resume: dict, assumed_skill_ids: list[str]) -> dict:
    original = compare_job(requires, resume.get("skills") or [])
    by_id = {row.get("skill_id"): row for row in resume.get("skills") or []}
    assumed = [sid for sid in dict.fromkeys(assumed_skill_ids) if sid in original["allowed_skill_ids"]]
    simulated_skills = [row for sid, row in by_id.items() if sid not in assumed]
    simulated_skills.extend({"skill_id": sid, "name": sid, "proficiency": "expert"} for sid in assumed)
    simulated = compare_job(requires, simulated_skills)
    return {
        "original_band": original["band"],
        "simulated_band": simulated["band"],
        "original_score": original["score"],
        "simulated_score": simulated["score"],
        "shift_set": simulated.get("path") or [],
        "allowed_skill_ids": original["allowed_skill_ids"],
        "assumed_skill_ids": assumed,
    }


def migration_map(jobs: list[dict], resume: dict) -> list[dict]:
    result = []
    for job in jobs[:3]:
        requires = job.get("requires") or []
        report = compare_job(requires, resume.get("skills") or [])
        target_names = {row.get("skill_id"): row.get("name") or row.get("skill_id") for row in requires}
        resume_names = {row.get("skill_id"): row.get("name") or row.get("skill_id") for row in resume.get("skills") or []}
        target_ids = set(target_names)
        resume_ids = set(resume_names)
        result.append(
            {
                "job_id": job.get("id"),
                "name": job.get("name") or job.get("id"),
                "band": report["band"],
                "minimum_shift_skill_count": len(report.get("shift_ids") or []),
                "shared_capabilities": sorted(target_names[sid] for sid in target_ids & resume_ids),
                "unique_requirements": sorted(target_names[sid] for sid in target_ids - resume_ids),
            }
        )
    return result


def market_signal_radar(watching: list[dict], jobs: list[dict], target_job_id: str) -> list[dict]:
    total_jobs = len(jobs)
    rows = []
    for signal in watching:
        sid = signal.get("skill_id")
        matches = [job for job in jobs if sid in {row.get("skill_id") for row in job.get("requires") or []}]
        evidence = [str(source.get("company") or source.get("id") or "") if isinstance(source, dict) else str(source)
                    for job in matches for source in job.get("sources") or []]
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


_NUM = re.compile(r"\d+(?:\.\d+)?%?")
ANALYSIS_PROMPT = (
    "Return JSON with keys one_sentence, positioning, rewrites, narrative. "
    "Chinese only. Use only facts in the user payload. Do not invent numbers, titles, companies, or results. "
    "one_sentence: 3 to 6 sentences naming the band, covered skills, gaps, and evidence quality. "
    "positioning: one paragraph on how this resume sits against the target job. "
    "rewrites: up to 5 items {original, problem, suggestion, facts_used, facts_to_add}. "
    "suggestion must rewrite the original, not copy it. Missing numbers go into facts_to_add as 待补 placeholders inside suggestion. "
    "narrative: a spoken interview self-introduction for 45 to 60 seconds (about 180 to 250 Chinese characters) "
    "using the person's role, experience, projects, and numbers from the resume. "
    "If facts are too thin, write a shorter honest version. No slogans."
)


def _names(rows: list[dict], limit: int = 8) -> list[str]:
    out = []
    for row in rows:
        name = str(row.get("name") or row.get("skill_id") or "").strip()
        if name and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def _join(parts: list[str]) -> str:
    return "、".join(part for part in parts if part)


def _invented_numbers(text: str, allowed: str) -> bool:
    return bool(set(_NUM.findall(text or "")) - set(_NUM.findall(allowed or "")))


def _rewrite_text(original: str, skill_name: str, level: str, job_name: str) -> dict:
    source = (original or "").strip()
    skill = skill_name or "该技能"
    clipped = source.rstrip("。.;；,，")
    if level == "result":
        suggestion = f"负责{skill}相关交付：{clipped}。该结果可直接用于{job_name}面试举证。"
        return {
            "original": source,
            "problem": "结果已写，但职责边界和岗位关键词还可以更清楚",
            "suggestion": suggestion,
            "facts_used": [source],
            "facts_to_add": [],
        }
    if level == "use":
        suggestion = f"负责{skill}：{clipped}。[待补：数据规模、延迟、成本或业务结果中的一项]"
        return {
            "original": source,
            "problem": "写了使用过程，但没有可核对的结果",
            "suggestion": suggestion,
            "facts_used": [source],
            "facts_to_add": ["规模、延迟、成本或业务结果中的一项"],
        }
    suggestion = f"在经历中使用{skill}完成[待补：具体任务]，结果为[待补：可核对指标]。当前原文只提到：{clipped}"
    return {
        "original": source,
        "problem": "只有提及，缺少任务中的使用与结果",
        "suggestion": suggestion,
        "facts_used": [source],
        "facts_to_add": ["使用该技能的任务", "可核对结果"],
    }


def _experience_rewrite(item: dict, kind: str) -> dict | None:
    original = str(item.get("summary") or "").strip()
    if not original:
        return None
    label = str(item.get("company") or item.get("name") or item.get("title") or kind)
    clipped = original.rstrip("。.;；,，")
    has_number = bool(_NUM.search(original))
    if has_number:
        suggestion = f"在{label}中，{clipped}。建议补一句本人职责边界，方便面试时按岗位要求展开。"
        problem = "已有结果数字，职责边界还可以写得更清楚"
        facts_to_add = ["本人职责边界"]
    else:
        suggestion = f"在{label}中，{clipped}。[待补：数据规模、延迟、成本或业务结果中的一项]"
        problem = f"{kind}描述缺少可核对结果"
        facts_to_add = ["规模、延迟、成本或业务结果中的一项"]
    return {
        "original": original,
        "problem": problem,
        "suggestion": suggestion,
        "facts_used": [original],
        "facts_to_add": facts_to_add,
    }


def _build_rewrites(fragments: list[dict], resume: dict, required_ids: set[str], skill_names: dict[str, str], job_name: str) -> list[dict]:
    ranked = []
    for fragment in fragments:
        original = str(fragment.get("text") or "").strip()
        if not original:
            continue
        sid = str(fragment.get("skill_id") or "")
        level = str(fragment.get("evidence_level") or "mention")
        required = 0 if sid in required_ids else 1
        ranked.append((required, {"mention": 0, "use": 1, "result": 2}.get(level, 0), fragment, original))
    ranked.sort(key=lambda row: (row[0], row[1]))
    rewrites = []
    seen = set()
    for _, _, fragment, original in ranked:
        if original in seen:
            continue
        seen.add(original)
        sid = str(fragment.get("skill_id") or "")
        rewrites.append(_rewrite_text(original, skill_names.get(sid) or sid, str(fragment.get("evidence_level") or "mention"), job_name))
    for item in resume.get("experiences") or []:
        row = _experience_rewrite(item, "经历")
        if row and row["original"] not in seen:
            seen.add(row["original"])
            rewrites.append(row)
    for item in resume.get("projects") or []:
        row = _experience_rewrite(item, "项目")
        if row and row["original"] not in seen:
            seen.add(row["original"])
            rewrites.append(row)
    return rewrites


def _build_narrative(job_name: str, resume: dict, strengths: list[dict], gaps: list[dict], covered_names: list[str]) -> str:
    profile = resume.get("profile") if isinstance(resume.get("profile"), dict) else {}
    role = str(profile.get("role") or "").strip() or "求职者"
    experience = str(resume.get("experience") or profile.get("experience") or "简历未标")
    education = str(resume.get("education") or "简历未标")
    paragraphs = [
        f"各位面试官好，我是{role}，工作经验{experience}，学历{education}。这次想应聘{job_name}。"
    ]
    for item in resume.get("experiences") or []:
        company = str(item.get("company") or "").strip() or "上一段工作"
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        span = "，".join(part for part in (item.get("start"), item.get("end")) if part)
        head = f"我在{company}" + (f"担任{title}" if title else "") + (f"（{span}）" if span else "")
        paragraphs.append(head + (f"，{summary.rstrip('。.')}。" if summary else "。"))
    for item in resume.get("projects") or []:
        name = str(item.get("name") or "一个项目").strip()
        summary = str(item.get("summary") or "").strip()
        paragraphs.append(f"项目方面，{name}" + (f"：{summary.rstrip('。.')}。" if summary else "。"))
    if strengths:
        quotes = [str(item.get("quote") or item.get("text") or "").strip() for item in strengths[:3]]
        paragraphs.append("和这个岗位直接相关、已经写在简历里的证据包括：" + "；".join(q.rstrip('。.') for q in quotes if q) + "。")
    elif covered_names:
        paragraphs.append(f"简历已经对齐到的技能有{_join(covered_names)}。")
    if gaps:
        gap_names = _join(_names(gaps, 6))
        paragraphs.append(f"对照{job_name}的正式要求，目前还缺{gap_names}的可核对证据。面试里我可以按项目把已有职责讲清楚，缺的结果数字我会在补简历时写上，而不是现场编造。")
    paragraphs.append("以上是按当前简历能核对的内容做的自我介绍。如果需要，我可以接着展开某一个项目的职责、规模和结果。")
    text = "\n\n".join(paragraphs)
    return text if len(text) <= 280 else text[:text.rfind("。", 0, 280) + 1] or paragraphs[0]


def _sanitize_rewrite(row: dict, original: str) -> dict | None:
    suggestion = str(row.get("suggestion") or "").strip()
    source = str(row.get("original") or original or "").strip()
    if not suggestion or not source or source not in original or suggestion == source:
        return None
    allowed = original
    if _invented_numbers(suggestion, allowed):
        return None
    facts_to_add = [str(item).strip() for item in (row.get("facts_to_add") or []) if str(item).strip()]
    facts_used = [str(item).strip() for item in (row.get("facts_used") or []) if str(item).strip()] or [source]
    if any(fact not in original for fact in facts_used):
        return None
    if not facts_to_add:
        return None
    suggestion = source.rstrip("。") + "。" + "；".join(f"【待补：{fact}】" for fact in facts_to_add)
    return {
        "original": source,
        "problem": str(row.get("problem") or "").strip() or "表达还可以更贴近岗位要求",
        "suggestion": suggestion,
        "facts_used": facts_used,
        "facts_to_add": facts_to_add,
    }


def _enrich_analysis(analysis: dict, *, job_name: str, resume: dict, core: dict, complete_json) -> dict:
    payload = {
        "job": job_name,
        "band": core.get("band"),
        "required_coverage": f"{core.get('req_cover'):g}/{core.get('req_full'):g}",
        "covered": _names(core.get("covered") or []),
        "gaps": _names(core.get("gaps") or []),
        "half": _names(core.get("half") or []),
        "role": (resume.get("profile") or {}).get("role") if isinstance(resume.get("profile"), dict) else "",
        "experience": resume.get("experience"),
        "education": resume.get("education"),
        "experiences": resume.get("experiences") or [],
        "projects": resume.get("projects") or [],
        "fragments": [
            {"text": row.get("text"), "level": row.get("evidence_level"), "skill": row.get("skill_id")}
            for row in (resume.get("evidence_fragments") or [])[:12]
        ],
        "rewrites": analysis.get("rewrites") or [],
    }
    result = complete_json(
        [
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user", "content": str(payload)},
        ]
    )
    if not isinstance(result, dict):
        return analysis
    model_rewrites = result.get("rewrites") if isinstance(result.get("rewrites"), list) else []
    merged = []
    originals = {row.get("original"): row for row in analysis.get("rewrites") or []}
    for row in model_rewrites:
        if not isinstance(row, dict):
            continue
        cleaned = _sanitize_rewrite(row, resume.get("preview_text") or "")
        if cleaned:
            merged.append(cleaned)
            originals.pop(cleaned["original"], None)
    for row in (analysis.get("rewrites") or []):
        if row.get("original") in {item.get("original") for item in merged}:
            continue
        merged.append(row)
    if merged:
        analysis["rewrites"] = merged
        analysis["actions"]["rewrite"] = merged[:5]
    # 岗位判断和求职叙事由已核对事实生成；模型只补充待补事实的提示。
    return analysis


def resume_analysis(*, job: dict, requires: list[dict], resume: dict, core: dict | None = None, complete_json=None) -> dict:
    core = core or compare_job(requires, resume.get("skills") or [])
    fragments = resume.get("evidence_fragments") or []
    evidence_by_skill = {row.get("skill_id"): row for row in fragments if row.get("skill_id")}
    skill_names = {str(row.get("skill_id")): str(row.get("name") or row.get("skill_id")) for row in requires if row.get("skill_id")}
    for row in resume.get("skills") or []:
        if row.get("skill_id"):
            skill_names.setdefault(str(row["skill_id"]), str(row.get("name") or row["skill_id"]))
    strengths = []
    for row in core.get("covered") or []:
        fragment = evidence_by_skill.get(row.get("skill_id"))
        if fragment:
            level = fragment.get("evidence_level") or "mention"
            label = {"result": "结果证据", "use": "使用证据", "mention": "提及"}.get(level, "提及")
            strengths.append(
                {
                    "text": f"{row.get('name') or row.get('skill_id')}已有{label}",
                    "evidence_fragment_id": fragment.get("id") or fragment.get("skill_id"),
                    "quote": fragment.get("text"),
                    "evidence_level": level,
                }
            )
        if len(strengths) == 3:
            break
    risks = [
        {
            "text": f"缺少{row.get('name') or row.get('skill_id')}的可核对证据",
            "check_scope": "经历、项目和技能栏",
            "requirement_id": row.get("skill_id"),
            "excerpt": row.get("excerpt") or "",
        }
        for row in (core.get("gaps") or [])[:3]
    ]
    states = []
    for row in requires:
        fragment = evidence_by_skill.get(row.get("skill_id"))
        states.append(
            {
                "skill_id": row.get("skill_id"),
                "name": row.get("name"),
                "state": "证据充分" if fragment and fragment.get("evidence_level") == "result" else "已提及但证据较弱" if fragment else "简历中未找到",
                "evidence_fragment_id": fragment.get("id") if fragment else None,
                "quote": fragment.get("text") if fragment else "",
                "check_scope": "经历、项目和技能栏" if not fragment else "引用的简历原文",
            }
        )
    job_name = job.get("name") or "目标岗位"
    band = core.get("band") or "不匹配"
    covered_names = _names(core.get("covered") or [])
    gap_names = _names(core.get("gaps") or [])
    half_names = _names(core.get("half") or [])
    required_ids = {str(row.get("skill_id")) for row in requires if row.get("kind") != "bonus" and row.get("skill_id")}
    rewrites = _build_rewrites(fragments, resume, required_ids, skill_names, job_name)
    capability = [
        {
            "skill_id": row.get("skill_id"),
            "name": row.get("name"),
            "why": f"补齐后用于换档，当前必备覆盖 {core.get('req_cover'):g}/{core.get('req_full'):g}",
            "excerpt": row.get("excerpt") or "",
            "deliverable": f"一段可核对的{row.get('name') or '该技能'}项目描述，写明职责、规模和结果",
            "url": row.get("url") or "",
        }
        for row in (core.get("path") or [])[:3]
    ]
    profile = resume.get("profile") if isinstance(resume.get("profile"), dict) else {}
    role = str(profile.get("role") or "").strip() or "未标注角色"
    experience = str(resume.get("experience") or profile.get("experience") or "简历未标")
    parts = [f"对照{job_name}，当前档位是{band}。必备覆盖 {core.get('req_cover'):g}/{core.get('req_full'):g}。"]
    if covered_names:
        parts.append(f"简历已证明：{_join(covered_names)}。")
    if half_names:
        parts.append(f"熟练级不足：{_join(half_names)}。")
    if gap_names:
        parts.append(f"尚未找到证据：{_join(gap_names)}。")
    else:
        parts.append("必备缺口已覆盖，下一步应把使用证据补成可核对结果。")
    result_count = sum(1 for item in states if item["state"] == "证据充分")
    mention_count = sum(1 for item in states if item["state"] == "已提及但证据较弱")
    missing_count = sum(1 for item in states if item["state"] == "简历中未找到")
    parts.append(f"按证据级统计：结果 {result_count} 项，仅提及 {mention_count} 项，未找到 {missing_count} 项。")
    blocker = risks[0]["text"] if risks else "暂无明确阻碍"
    analysis = {
        "one_sentence": "".join(parts),
        "core_judgments": {
            "fit_band": band,
            "advantage": strengths[0]["text"] if strengths else "尚未找到可引用的优势证据",
            "blocker": blocker,
        },
        "positioning": {
            "text": (
                f"按校对后的简历，你目前是{role}，工作年限{experience}。"
                f"在可诊断岗位里，这份材料更接近{job_name}，依据是档位「{band}」和已覆盖的必备技能。"
                f"主要阻碍是{blocker}。"
            ),
            "evidence_fragment_ids": [item.get("evidence_fragment_id") for item in strengths],
            "check_scope": "简历全文与当前可诊断岗位集合",
        },
        "strengths": strengths,
        "risks": risks,
        "content_states": states,
        "gap_detail": [
            {"skill_id": row.get("skill_id"), "name": row.get("name"), "excerpt": row.get("excerpt") or "", "cover": row.get("cover")}
            for row in (core.get("gaps") or [])[:8]
        ],
        "evidence_map": evidence_map(requires, resume),
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
        "narrative": _build_narrative(job_name, resume, strengths, core.get("gaps") or [], covered_names),
    }
    if complete_json is not None:
        analysis = _enrich_analysis(analysis, job_name=job_name, resume=resume, core=core, complete_json=complete_json)
    return analysis


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
    try:
        from app.llm.client import complete_json as llm_json
    except Exception:
        llm_json = None
    core["path"] = attach_urls(core["path"])
    analysis = resume_analysis(job=job, requires=requires, resume=resume, core=core, complete_json=llm_json)
    url_by_id = {step.get("skill_id"): step.get("url") or "" for step in core["path"]}
    for item in analysis.get("actions", {}).get("capability") or []:
        if not item.get("url"):
            item["url"] = url_by_id.get(item.get("skill_id")) or ""
    summary = (
        f"对照{job.get('name') or '目标岗'}，档位「{core['band']}」。"
        f"必备覆盖 {core['req_cover']:g}/{core['req_full']:g}。"
        f"缺口 {len(core.get('gaps') or [])} 项，半档 {len(core.get('half') or [])} 项。"
    )
    names = {row["skill_id"]: row.get("name") or row["skill_id"] for row in requires}
    neighbors = [
        {"job_id": job["id"], "name": job.get("name") or job["id"], "band": core["band"]}
    ]
    migrate_jobs = [{"id": job["id"], "name": job.get("name") or job["id"], "requires": requires}]
    if neighbor:
        nrep = compare_job(neighbor["requires"], resume.get("skills") or [])
        neighbors.append(
            {
                "job_id": neighbor["job"]["id"],
                "name": neighbor["job"]["name"],
                "band": nrep["band"],
            }
        )
        migrate_jobs.append({"id": neighbor["job"]["id"], "name": neighbor["job"]["name"], "requires": neighbor["requires"]})
    return {
        "job_id": job["id"],
        "session_id": resume.get("session_id"),
        "graph_release": resume.get("graph_release"),
        "metadata": {
            "graph_release": resume.get("graph_release"),
            "evidence_count": len({source for row in requires for source in row.get("sources") or []}),
            "f1": None,
            "evaluation_note": "本发布尚未绑定真实模型评测，不展示历史或模拟 F1",
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
                    for sid in core["shift_ids"] if len(core["shift_ids"]) <= PATH_MAX
                ],
                "minimum_shift_skill_count": len(core["shift_ids"]),
            },
            "locate": {
                "neighbors": neighbors,
                "hits": [
                    {"skill_id": row["skill_id"], "name": row["name"], "cover": row.get("cover")}
                    for row in core["covered"]
                ],
                "migration_map": migration_map(migrate_jobs, resume),
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
