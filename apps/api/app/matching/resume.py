from __future__ import annotations

import io
import re
from concurrent.futures import ThreadPoolExecutor

from app.pipeline.align import align_skill
from app.pipeline.extract import _PROF, _alias


class ResumeError(ValueError):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def extract_text(data: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".doc") and not name.endswith(".docx"):
        raise ResumeError("不支持 .doc，请上传 PDF 或 docx")
    if name.endswith(".docx"):
        return _docx_text(data)
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        return _pdf_text(data)
    raise ResumeError("请上传 PDF 或 docx")


def _pdf_text(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > 30:
            raise ResumeError("PDF 不能超过 30 页")
        parts = [(page.extract_text() or "") for page in pdf.pages]
    text = "\n".join(parts).strip()
    if not text:
        raise ResumeError("扫描件没有文本层")
    if len(text) > 50_000:
        raise ResumeError("提取文本不能超过 50,000 字符")
    return text


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs).strip()
    if not text:
        raise ResumeError("文档没有可提取的文本")
    if len(text) > 50_000:
        raise ResumeError("提取文本不能超过 50,000 字符")
    return text


def _name_in_text(name: str, blob: str) -> bool:
    needle = (name or "").casefold()
    if not needle:
        return False
    if re.search(r"[\u4e00-\u9fff]", needle):
        return needle in blob
    return re.search(rf"(?<![a-z0-9_]){re.escape(needle)}(?![a-z0-9_])", blob) is not None


def evidence_level(text: str, name: str) -> str:
    """Classify only what the sentence visibly proves."""
    sentence = next((part.strip() for part in re.split(r"[\n。.!！]", text or "") if _name_in_text(name, part)), "") or (text or "").strip()
    if not sentence:
        return "mention"
    has_result = bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|ms|秒|万|qps|次)?", sentence, re.I)) and bool(
        re.search(r"负责|主导|交付|实现|提升|降低|built|led|delivered|improv|reduc", sentence, re.I)
    )
    if has_result:
        return "result"
    if re.search(r"负责|使用|开发|构建|维护|实现|参与|used|built|develop|worked", sentence, re.I):
        return "use"
    return "mention"


def _sentence_for(text: str, names: list[str]) -> str:
    for sentence in re.split(r"[\n。.!！]", text or ""):
        if any(_name_in_text(name, sentence) for name in names if name):
            return sentence.strip()
    return ""


def _evidence_fragments(text: str, skills: list[dict], index: list[dict]) -> list[dict]:
    by_id = {row.get("id"): row for row in index}
    fragments = []
    for skill in skills:
        vocab = by_id.get(skill.get("skill_id"), {})
        names = [vocab.get("name") or skill.get("name") or "", *(vocab.get("synonyms") or [])]
        excerpt = skill.get("llm_excerpt") or _sentence_for(text, names)
        if excerpt and excerpt not in text:
            excerpt = _sentence_for(text, names)
        if not excerpt:
            continue
        fragments.append(
            {
                "skill_id": skill["skill_id"],
                "text": excerpt,
                "section": "project" if re.search(r"项目|project", excerpt, re.I) else "experience",
                "evidence_level": evidence_level(excerpt, names[0]),
            }
        )
    return fragments


INFO_PROMPT = (
    "Extract resume JSON. Fields: experience, education. "
    "experience is a short years string like 3年, or 简历未标. "
    "education is a short school/degree string, or 简历未标. "
    "Do not invent. No other enum values."
)
SKILL_PROMPT = (
    "Extract resume skills JSON: {skills:[{name, proficiency}]}. "
    "Omit proficiency unless the resume explicitly marks a level "
    "(了解/aware, 熟练/able, 精通/expert). Do not guess. "
    "Prefer names from this vocabulary.\n"
    "vocabulary: "
)


def parse_resume(
    text: str,
    index: list[dict],
    complete_json=None,
    *,
    threshold: float | None = None,
    strict: bool = False,
) -> dict:
    if complete_json is None:
        from app.llm.client import complete_json as complete_json
    blob = (text or "")[:8000]
    vocab = "、".join(row.get("name") or "" for row in index if row.get("name"))
    info_messages = [
        {"role": "system", "content": INFO_PROMPT},
        {"role": "user", "content": blob},
    ]
    skill_messages = [
        {"role": "system", "content": SKILL_PROMPT + vocab},
        {"role": "user", "content": blob},
    ]

    def _call(messages):
        try:
            payload = complete_json(messages)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            if strict:
                raise
            return {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        info_f = pool.submit(_call, info_messages)
        skill_f = pool.submit(_call, skill_messages)
        info = info_f.result()
        raw_skills = skill_f.result()
    skills = _align_skills(raw_skills.get("skills") or [], index, threshold=threshold)
    if not skills:
        skills = skills_from_text(text, index, threshold=threshold)
    for row in skills:
        if not _marks_level_for_skill(text, row.get("name") or ""):
            row["proficiency"] = None
    fallback = _resume_info_from_text(text)
    experience = str(info.get("experience") or "").strip()
    education = str(info.get("education") or "").strip()
    experience = ("" if experience == "简历未标" else experience) or fallback["experience"] or "简历未标"
    education = ("" if education == "简历未标" else education) or fallback["education"] or "简历未标"
    fragments = _evidence_fragments(text, skills, index)
    return {
        "profile": {"role": "", "experience": experience},
        "education": education,
        "education_items": [{"text": education}] if education != "简历未标" else [],
        "experiences": [],
        "projects": [],
        "experience": experience,
        "education_text": education,
        "skills": skills,
        "evidence_fragments": fragments,
        "date_conflicts": date_conflicts(text),
        "user_added": [],
    }


def date_conflicts(text: str) -> list[dict]:
    ranges = []
    for match in re.finditer(r"(20\d{2})[./-](\d{1,2}).{0,3}(20\d{2})[./-](\d{1,2})", text or ""):
        start = int(match.group(1)) * 12 + int(match.group(2))
        end = int(match.group(3)) * 12 + int(match.group(4))
        if end < start:
            ranges.append({"text": match.group(0), "reason": "结束时间早于开始时间"})
        ranges.append({"start": start, "end": end, "text": match.group(0)})
    conflicts = []
    for i, left in enumerate(ranges):
        for right in ranges[i + 1 :]:
            if "start" in left and "start" in right and max(left["start"], right["start"]) <= min(left["end"], right["end"]):
                conflicts.append({"left": left["text"], "right": right["text"], "reason": "经历时间重叠"})
    return conflicts


def _marks_level_for_skill(text: str, name: str) -> bool:
    blob = text or ""
    needle = re.escape(name)
    return re.search(rf"(?:了解|熟练|精通|aware|able|expert|proficient)\s*(?:掌握|使用|过)?\W{{0,12}}{needle}", blob, re.I) is not None


def _resume_info_from_text(text: str) -> dict:
    # ponytail: explicit common formats only; use structured parsing for multilingual employment histories.
    blob = text or ""
    experience = re.search(r"\b(\d+)\s*(?:年|years?)\s*(?:工作|经验|experience)?", blob, re.I)
    education = re.search(r"\b(Bachelor|Master|PhD)\b|(?:博士|硕士|本科|大专)(?:学历|学位)?", blob, re.I)
    return {
        "experience": f"{experience.group(1)}年" if experience else "",
        "education": education.group(0) if education else "",
    }


def _align_skills(rows: list, index: list[dict], *, threshold: float | None = None) -> list[dict]:
    found = []
    seen: set[str] = set()
    for raw in rows:
        if isinstance(raw, str):
            raw = {"name": raw}
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        hit = align_skill(name, index, threshold=threshold)
        if hit is None or hit["id"] in seen:
            continue
        seen.add(hit["id"])
        marked = str(raw.get("proficiency") or "").strip()
        proficiency = _alias(_PROF, marked, "") if marked else ""
        if proficiency not in ("aware", "able", "expert"):
            proficiency = None
        found.append(
            {
                "skill_id": hit["id"],
                "name": hit.get("name") or name,
                "proficiency": proficiency,
                "llm_excerpt": str(raw.get("evidence") or raw.get("excerpt") or "").strip(),
            }
        )
    return found


def skills_from_text(text: str, index: list[dict], *, threshold: float | None = None) -> list[dict]:
    # ponytail: name+synonym substring; cosine via align_skill when resume phrases diverge from Skill.name
    blob = (text or "").casefold()
    found = []
    seen: set[str] = set()
    for skill in index:
        names = [skill.get("name") or "", *(skill.get("synonyms") or [])]
        if not any(_name_in_text(n, blob) for n in names):
            continue
        sid = skill["id"]
        if sid in seen:
            continue
        seen.add(sid)
        found.append(
            {
                "skill_id": sid,
                "name": skill.get("name") or names[0],
                "proficiency": None,
            }
        )
    return found
