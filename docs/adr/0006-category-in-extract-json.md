# 技能类目写在同一次 JD 抽取里

技能类目一期固定五桶。不为每个技能点再打一轮 LLM，也不靠纯词表把中文复合名塞进「领域知识」。`complete_json` 抽 JD 时每个技能点带上 `category` 枚举，合并技能点按多数票归桶；Python / FastAPI 这类铁名可用词表否决。`init_graph` 写入五个 `SkillCategory` 节点，入谱时写 `IN_CATEGORY`。
