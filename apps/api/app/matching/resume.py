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
        parts = [(page.extract_text() or "") for page in pdf.pages]
    text = "\n".join(parts).strip()
    if not text:
        raise ResumeError("扫描件没有文本层")
    return text


def _docx_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs).strip()
    if not text:
        raise ResumeError("文档没有可提取的文本")
    return text


def _name_in_text(name: str, blob: str) -> bool:
    needle = (name or "").casefold()
    if not needle:
        return False
    if re.search(r"[\u4e00-\u9fff]", needle):
        return needle in blob
    return re.search(rf"(?<![a-z0-9_]){re.escape(needle)}(?![a-z0-9_])", blob) is not None


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


def parse_resume(text: str, index: list[dict], complete_json=None) -> dict:
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
            payload = complete_json(None, messages)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=2) as pool:
        info_f = pool.submit(_call, info_messages)
        skill_f = pool.submit(_call, skill_messages)
        info = info_f.result()
        raw_skills = skill_f.result()
    skills = _align_skills(raw_skills.get("skills") or [], index)
    if not skills:
        skills = skills_from_text(text, index)
    for row in skills:
        if not _marks_level_for_skill(text, row.get("name") or ""):
            row["proficiency"] = None
    fallback = _resume_info_from_text(text)
    experience = str(info.get("experience") or "").strip()
    education = str(info.get("education") or "").strip()
    experience = ("" if experience == "简历未标" else experience) or fallback["experience"] or "简历未标"
    education = ("" if education == "简历未标" else education) or fallback["education"] or "简历未标"
    return {"experience": experience, "education": education, "skills": skills}


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


def _align_skills(rows: list, index: list[dict]) -> list[dict]:
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
        hit = align_skill(name, index)
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
            }
        )
    return found


def skills_from_text(text: str, index: list[dict]) -> list[dict]:
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


def minimal_pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 24 720 Td ({safe}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    body = b"%PDF-1.1\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    out = body + f"xref\n0 6\n0000000000 65535 f \n".encode()
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out
