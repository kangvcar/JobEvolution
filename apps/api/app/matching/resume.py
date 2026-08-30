from __future__ import annotations

import io
import re


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
    if len(needle) <= 2:
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", blob) is not None
    return needle in blob


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
