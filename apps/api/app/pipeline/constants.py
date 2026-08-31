import os

COVERAGE_THRESHOLD = 0.30
ALIGN_THRESHOLD = float(os.environ.get("ALIGN_THRESHOLD", "0.85"))
JOB_ALIGN_THRESHOLD = 0.80
EXTRACT_RETRY = 1
EXTRACT_WORKERS = int(os.environ.get("EXTRACT_WORKERS", "8"))
PASSTHROUGH_KEY = "gate:passthrough"
EMERGING_SOURCES = 3
EMERGING_WINDOW_DAYS = 90
FORMED_SOURCES = 10
FORMED_MONTHS = 6
DISCOVER_MIN_CLUSTER = 3

SKILL_CATEGORIES = {
    "language": "语言",
    "framework": "框架",
    "platform": "平台",
    "engineering": "工程",
    "domain": "领域知识",
}

# 铁名否决：这些名字的类目不信任 LLM 投票（ADR-0006）。
SKILL_IRON_CATEGORY = {
    "python": "language",
    "java": "language",
    "javascript": "language",
    "typescript": "language",
    "golang": "language",
    "rust": "language",
    "c++": "language",
    "scala": "language",
    "sql": "language",
    "fastapi": "framework",
    "django": "framework",
    "flask": "framework",
    "spring": "framework",
    "langchain": "framework",
    "pytorch": "framework",
    "tensorflow": "framework",
    "react": "framework",
    "vue": "framework",
    "docker": "platform",
    "kubernetes": "platform",
    "k8s": "platform",
    "flink": "platform",
    "spark": "platform",
    "hadoop": "platform",
    "kafka": "platform",
}
