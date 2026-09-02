from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.pipeline.constants import SKILL_CATEGORIES, SKILL_DEFINITION
from app.targets import JOB_TARGET_NAMES

# 单段抽取。曾试验两段式（先列表后补字段，ADR-0012 草案），实测 R 反降
# （0.729 → 0.604，enrich 丢名单项），回退单段；列表行为已由金标起草侧验证。
FEWSHOT = (
    "示例——输入：\n"
    "title: 后端开发工程师\n"
    "domain: ai\n"
    "body:\n"
    "岗位职责：负责数据接口与检索服务开发，参与数据建模。\n"
    "任职要求：熟练掌握 Python 与 SQL，熟悉 C/C++；具备良好的沟通能力与团队合作精神。\n"
    "输出（只保留原子技术技能；通用能力和无动作品牌不进正式要求）：\n"
    '{"job_name": "后端开发工程师", "domain": "ai", "target": "", "skills": ['
    '{"name": "Python", "kind": "required", "proficiency": "able", "confidence": 0.9, '
    '"excerpt": "熟练掌握 Python", "section": "requirement", "category": "language"}, '
    '{"name": "SQL", "kind": "required", "proficiency": "able", "confidence": 0.9, '
    '"excerpt": "熟练掌握 Python 与 SQL", "section": "requirement", "category": "language"}, '
    '{"name": "检索", "kind": "required", "proficiency": "able", "confidence": 0.8, '
    '"excerpt": "检索服务开发", "section": "duty", "category": "domain"}, '
    '{"name": "数据建模", "kind": "required", "proficiency": "able", "confidence": 0.8, '
    '"excerpt": "参与数据建模", "section": "duty", "category": "domain"}, '
    '{"name": "C", "kind": "required", "proficiency": "able", "confidence": 0.7, '
    '"excerpt": "熟悉 C/C++", "section": "requirement", "category": "language"}, '
    '{"name": "C++", "kind": "required", "proficiency": "able", "confidence": 0.7, '
    '"excerpt": "熟悉 C/C++", "section": "requirement", "category": "language"}, '
    '{"name": "沟通能力", "candidate_type": "generic", "kind": "required", '
    '"proficiency": "aware", "confidence": 0.6, "excerpt": "具备良好的沟通能力", '
    '"section": "requirement", "category": "domain"}]}'
)

SYSTEM_PROMPT = (
    "从 JD 抽取 JSON。字段：job_name、domain、target、skills。"
    + SKILL_DEFINITION + " "
    "逐句检查职责与要求段，句中出现的每一个技能点都要列出，宁全勿缺："
    "工具与方法、带职责上下文的领域知识都要收，不要因为已经列了很多而省略其余。"
    "三点边界：沟通、团队协作、学习能力等通用素质不进入技能点；"
    "GPT、Gemini、ChatGLM 等品牌默认只留在证据上下文，没有动作不产生正式技能；"
    "只有职责上下文充分时才保留 CV、NLP 等宽泛领域词。并列串写的技术要拆开，"
    "「C/C++/Java」拆成 C、C++、Java 三条；技能点名用原文的完整词。"
    + FEWSHOT +
    "domain 必须是 ai、data、system、iot 之一。"
    "target 是岗位标题能对上的规范岗位名，对不上则为空，候选："
    f"{'、'.join(JOB_TARGET_NAMES)}。"
    "每个技能点字段：name、kind、proficiency、confidence、excerpt、section、category、"
    "raw_name、action、context、candidate_type。candidate_type 只能是 skill、brand、generic、"
    "broad_domain、unknown。"
    "vote 只能 required_explicit、bonus_explicit、unmarked；kind 仅为兼容字段，可为 required 或 bonus；"
    "proficiency 只能 aware、able、expert；"
    "section 只能 duty 或 requirement；category 必须是："
    + ", ".join(SKILL_CATEGORIES)
    + "。confidence 为 0-1。excerpt 是包含该技能点的最短原文片段。"
    "字段拿不准时给保守默认值（kind=required、proficiency=able、confidence=0.5、candidate_type=unknown），"
    "但正文里写出的技能点一个都不能因为字段拿不准而漏掉。"
    "不要发明枚举值。"
)

_KIND = {
    "required": "required",
    "bonus": "bonus",
    "must": "required",
    "core": "required",
    "technical": "required",
    "skill": "required",
    "必备": "required",
    "要求": "required",
    "plus": "bonus",
    "optional": "bonus",
    "nice": "bonus",
    "加分": "bonus",
}

_PROF = {
    "aware": "aware",
    "able": "able",
    "expert": "expert",
    "beginner": "aware",
    "basic": "aware",
    "familiar": "aware",
    "了解": "aware",
    "intermediate": "able",
    "proficient": "able",
    "熟练": "able",
    "advanced": "expert",
    "master": "expert",
    "精通": "expert",
}

_SECTION = {
    "duty": "duty",
    "duties": "duty",
    "responsibility": "duty",
    "responsibilities": "duty",
    "职责": "duty",
    "requirement": "requirement",
    "requirements": "requirement",
    "任职": "requirement",
    "benefit": "benefit",
    "benefits": "benefit",
    "welfare": "benefit",
    "福利": "benefit",
    "intro": "intro",
    "company": "intro",
    "介绍": "intro",
}

_DOMAIN = {
    "ai": "ai",
    "data": "data",
    "system": "system",
    "iot": "iot",
    "人工智能": "ai",
    "大数据": "data",
    "智能系统": "system",
    "物联网": "iot",
}

_CATEGORY = {cid: cid for cid in SKILL_CATEGORIES}
_CATEGORY.update(
    {
        "语言": "language",
        "框架": "framework",
        "平台": "platform",
        "工程": "engineering",
        "领域": "domain",
        "领域知识": "domain",
    }
)

_TARGETS = {name.casefold(): name for name in JOB_TARGET_NAMES}

# Deterministic guardrails are deliberately small. The model may propose a
# type, but these names win at the trust boundary before a graph fact is made.
GENERIC_SKILL_NAMES = frozenset(
    {
        "沟通能力", "沟通", "团队协作", "团队合作", "团队合作精神", "跨团队协作",
        "学习能力", "责任心", "抗压能力", "问题解决", "表达能力", "自我驱动",
        "编程习惯", "数学", "计算机", "算法", "computer science",
    }
)
BRAND_NAMES = frozenset({"gpt", "gemini", "chatglm", "mixtral-7b", "llama2", "llama 2"})
BROAD_DOMAIN_NAMES = frozenset({"cv", "nlp", "计算机视觉", "自然语言处理"})
BRAND_ACTIONS = (
    ("API 集成", ("api", "接口", "调用")),
    ("模型部署", ("部署", "上线", "推理服务")),
    ("模型微调", ("微调", "fine-tune", "finetune")),
    ("模型评测", ("评测", "评估", "benchmark")),
)


def classify_skill_candidate(name: str, *, action: str = "", context: str = "", candidate_type: str = "") -> str:
    """Return the graph-ingest type without relying on an LLM classification."""
    folded = (name or "").strip().casefold()
    hinted = (candidate_type or "").strip().casefold()
    if folded in GENERIC_SKILL_NAMES or hinted == "generic":
        return "generic"
    if folded in BRAND_NAMES or hinted == "brand":
        return "brand"
    if folded in BROAD_DOMAIN_NAMES or hinted == "broad_domain":
        return "broad_domain"
    return "skill"


def brand_action_skill(name: str, action: str, context: str = "") -> str | None:
    if classify_skill_candidate(name, candidate_type="brand") != "brand":
        return None
    evidence = f"{action} {context}".casefold()
    for derived, markers in BRAND_ACTIONS:
        if any(marker in evidence for marker in markers):
            return derived
    return None


class ExtractedSkill(BaseModel):
    name: str
    kind: Literal["required", "bonus"]
    proficiency: Literal["aware", "able", "expert"]
    confidence: float = Field(ge=0, le=1)
    excerpt: str = ""
    section: Literal["duty", "requirement", "benefit", "intro"] = "requirement"
    category: Literal["", "language", "framework", "platform", "engineering", "domain"] = ""
    # These fields keep the model's observation separate from the graph fact.
    # `candidate_type` is a hint only; gate.py applies the deterministic policy.
    raw_name: str = ""
    action: str = ""
    context: str = ""
    candidate_type: Literal["skill", "brand", "generic", "broad_domain", "unknown"] = "unknown"
    vote: Literal["required_explicit", "bonus_explicit", "unmarked"] = "unmarked"
    group_id: str = ""
    min_required: int = Field(default=1, ge=1)


class ExtractedJd(BaseModel):
    job_name: str = Field(min_length=1)
    domain: str = "ai"
    target: str = ""
    skills: list[ExtractedSkill] = Field(default_factory=list)


def _alias(table: dict[str, str], value, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    folded = text.casefold()
    if folded in table:
        return table[folded]
    if text in table:
        return table[text]
    return default


def _confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if number > 1:
        number = number / 100.0
    return min(1.0, max(0.0, number))


_VOTE = {
    "required_explicit": "required_explicit",
    "required": "required_explicit",
    "must": "required_explicit",
    "必备": "required_explicit",
    "bonus_explicit": "bonus_explicit",
    "bonus": "bonus_explicit",
    "plus": "bonus_explicit",
    "加分": "bonus_explicit",
    "unmarked": "unmarked",
    "未标": "unmarked",
}


def requirement_vote(value, *, excerpt: str = "", section: str = "requirement") -> str:
    raw = str(value or "").strip().casefold()
    if raw in _VOTE:
        vote = _VOTE[raw]
    elif section == "requirement":
        vote = "required_explicit"
    else:
        vote = "unmarked"
    if vote == "required_explicit" and section != "requirement":
        markers = ("必须", "要求", "熟练掌握", "任职资格", "任职要求")
        if not any(marker in (excerpt or "") for marker in markers):
            return "unmarked"
    return vote


def _positive_int(value, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def coerce_extracted(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"job_name": "", "domain": "ai", "target": "", "skills": []}
    skills = []
    for raw in payload.get("skills") or []:
        if isinstance(raw, str):
            raw = {"name": raw}
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        skills.append(
            {
                "name": name,
                "kind": _alias(_KIND, raw.get("kind"), "required"),
                "proficiency": _alias(_PROF, raw.get("proficiency"), "able"),
                "confidence": _confidence(raw.get("confidence")),
                "excerpt": str(raw.get("excerpt") or "").strip(),
                "section": _alias(_SECTION, raw.get("section"), "requirement"),
                "category": _alias(_CATEGORY, raw.get("category"), ""),
                "raw_name": str(raw.get("raw_name") or raw.get("name") or "").strip(),
                "action": str(raw.get("action") or "").strip(),
                "context": str(raw.get("context") or "").strip(),
                "candidate_type": _alias(
                    {
                        "skill": "skill",
                        "technical": "skill",
                        "brand": "brand",
                        "generic": "generic",
                        "broad_domain": "broad_domain",
                        "domain": "broad_domain",
                    },
                    raw.get("candidate_type"),
                    "unknown",
                ),
                "vote": requirement_vote(
                    raw.get("vote") or raw.get("kind"),
                    excerpt=str(raw.get("excerpt") or "").strip(),
                    section=_alias(_SECTION, raw.get("section"), "requirement"),
                ),
                "group_id": str(raw.get("group_id") or raw.get("group") or "").strip(),
                "min_required": _positive_int(raw.get("min_required")),
            }
        )
    domain = _alias(_DOMAIN, payload.get("domain"), "ai")
    target = _TARGETS.get(str(payload.get("target") or "").strip().casefold(), "")
    return {
        "job_name": str(payload.get("job_name") or "").strip(),
        "domain": domain,
        "target": target,
        "skills": skills,
    }


def parse_extracted(complete_json, snapshot: dict | None = None) -> ExtractedJd:
    snap = snapshot or {}
    body = snap.get("body") or ""
    if body:
        # 只喂职责/要求段：与金标 section 规则一致，福利/介绍不再进模型视野
        from app.pipeline.sections import split_sections

        parts = split_sections(body)
        body = f"{parts['duty']}\n{parts['requirement']}".strip() or body
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"title: {snap.get('title') or ''}\n"
                f"domain: {snap.get('domain') or ''}\n"
                f"body:\n{body}"
            ),
        },
    ]
    try:
        payload = complete_json(messages)
    except Exception as exc:
        raise ValueError("extract json failed") from exc
    return ExtractedJd.model_validate(coerce_extracted(payload))
