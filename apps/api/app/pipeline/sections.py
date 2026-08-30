from __future__ import annotations

_HEADS = (
    ("benefit", ("薪酬福利", "福利待遇", "岗位福利", "福利")),
    ("intro", ("公司介绍", "关于我们", "公司简介")),
    ("duty", ("岗位职责", "工作职责", "职责描述", "职责")),
    ("requirement", ("任职资格", "任职要求", "岗位要求", "要求")),
)


def split_sections(body: str) -> dict[str, str]:
    text = body or ""
    hits: list[tuple[int, str]] = []
    for section, names in _HEADS:
        for name in names:
            pos = text.find(name)
            if pos >= 0:
                hits.append((pos, section))
                break
    hits.sort()
    parts = {"duty": "", "requirement": "", "benefit": "", "intro": ""}
    if not hits:
        parts["requirement"] = text
        return parts
    if hits[0][0] > 0:
        parts["requirement"] += text[: hits[0][0]]
    for i, (pos, section) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        parts[section] += text[pos:end]
    return parts


def section_of(body: str, excerpt: str) -> str:
    if not excerpt:
        return "requirement"
    parts = split_sections(body)
    for name in ("benefit", "intro", "duty", "requirement"):
        if excerpt in parts[name]:
            return name
    return "requirement"
