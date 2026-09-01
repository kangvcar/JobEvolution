import os

# ADR-0012：技能点定义的唯一权威出处。金标起草（app/eval/draft.py）与管线抽取
# （app/pipeline/extract.py）共用这一段——定义同步、提示词各自成文。
# 改这里 = 改技能点规格 = 金标须按 ADR-0011 重新起草裁决。
SKILL_DEFINITION = (
    "技能点指原文中明确写出的：工具、语言、框架、平台、方法、领域知识。"
    "只从原文提取，逐字或最小归一化；原文没写的不要推断，不要泛化成类目名。"
)

COVERAGE_THRESHOLD = 0.30
# 0.70 为 bge-m3 余弦校准值（金标 mention 变体互近邻配对，F1 峰值），哈希兜底时代是 0.85
ALIGN_THRESHOLD = float(os.environ.get("ALIGN_THRESHOLD", "0.70"))
# 0.84 为 bge-m3 岗位名校准值：17 靶子两两最高 0.828，别名变体（大模型应用开发工程师）0.965 起步；
# 更近的别名（LLM 业务工程师 0.562）余弦够不着，留给簇判别写 ALIAS_OF。哈希兜底时代是 0.80
JOB_ALIGN_THRESHOLD = 0.84
EXTRACT_WORKERS = int(os.environ.get("EXTRACT_WORKERS", "8"))
PASSTHROUGH_KEY = "gate:passthrough"
EMERGING_SOURCES = 3
EMERGING_WINDOW_DAYS = 90
FORMED_SOURCES = 10
FORMED_MONTHS = 6
DISCOVER_MIN_CLUSTER = 3

# 选样口径（工单 #73 / ADR-0009）：标题子串只当进闸预筛。
ALIAS_PRE_FILTER = (
    "大模型应用开发",
    "大模型应用研发",
    "大模型开发",
    "Agent",
    "智能体",
    "Prompt",
    "实时计算",
    "Flink",
    "嵌入式AI",
)
FAT_JOB_SOURCES = 30
FAT_SLICE_CAP = 8
ALIAS_CAP = 20
EXTRACT_CACHE_VERSION = 4

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
