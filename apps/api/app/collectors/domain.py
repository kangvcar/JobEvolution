"""Coarse title filter into the four domains. 人工智能 wins on overlap."""

from __future__ import annotations

import re

# ASCII tokens ≤3 letters use word boundaries so "AI" does not match "JAVA".
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai": (
        "人工智能",
        "大模型",
        "大语言",
        "机器学习",
        "深度学习",
        "神经网络",
        "计算机视觉",
        "自然语言",
        "多模态",
        "智能体",
        "提示词",
        "知识图谱",
        "推荐系统",
        "推荐算法",
        "生成式",
        "模型评测",
        "模型训练",
        "端侧推理",
        "推理引擎",
        "算法",
        "AIGC",
        "LLM",
        "GPT",
        "NLP",
        "MLOps",
        "Prompt",
        "Agent",
        "AI",
    ),
    "data": (
        "大数据",
        "数据工程师",
        "数据分析师",
        "数据科学家",
        "数据分析",
        "数据科学",
        "数据开发",
        "数据仓库",
        "数据平台",
        "数据治理",
        "数据架构",
        "数据挖掘",
        "实时计算",
        "商业智能",
        "数仓",
        "Data Scientist",
        "Data Engineer",
        "Data Analyst",
        "ClickHouse",
        "Spark",
        "Flink",
        "Hive",
        "ETL",
        "BI",
    ),
    "system": (
        "智能系统",
        "嵌入式",
        "自动驾驶",
        "智能驾驶",
        "无人驾驶",
        "机器人",
        "智能硬件",
        "具身",
        "工控",
        "单片机",
        "固件",
        "车载",
        "SLAM",
        "RTOS",
        "MCU",
        "PLC",
        "ROS",
    ),
    "iot": (
        "物联网",
        "边缘计算",
        "传感器",
        "智慧城市",
        "智慧交通",
        "智慧园区",
        "NB-IoT",
        "MQTT",
        "LoRa",
        "IoT",
    ),
}

DOMAIN_PRIORITY = ("ai", "data", "system", "iot")

_BOUNDARY = {}
for _kw in {k for kws in DOMAIN_KEYWORDS.values() for k in kws}:
    if _kw.isascii() and len(_kw) <= 3:
        _BOUNDARY[_kw.lower()] = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(_kw)}(?![A-Za-z0-9])",
            re.I,
        )


def _title_has(title: str, keyword: str) -> bool:
    bounded = _BOUNDARY.get(keyword.lower())
    if bounded is not None:
        return bounded.search(title) is not None
    if keyword.isascii():
        return keyword.lower() in title.lower()
    return keyword in title


def classify_domain(title: str) -> str | None:
    text = (title or "").strip()
    if not text:
        return None
    for domain in DOMAIN_PRIORITY:
        if any(_title_has(text, keyword) for keyword in DOMAIN_KEYWORDS[domain]):
            return domain
    return None
