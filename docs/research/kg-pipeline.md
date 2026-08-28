# 调研:LLM 知识图谱构建管线与图存储选型

> 对应工单:[#3](https://github.com/kangvcar/JobEvolution/issues/3) · 调研日期:2026-08-28
>
> 约束回顾:LLM 使用 DeepSeek 官方 API(OpenAI 兼容端点);后端 Python + FastAPI;单机 docker-compose 部署;图规模约千级岗位 × 万级技能点(节点总量数万、边十万级以内);需支撑「演化事件」(能力项新增/删除/修改)按时间查询与回放。

## 一、结论速览

- **图存储推荐:Neo4j Community Edition**(docker-compose 单容器),时间维度用「关系有效期 + 演化事件节点」建模;备选为 PG + Apache AGE(仅当团队想把关系数据和图合并进一个 PostgreSQL 时)。KuzuDB 因项目已归档**不建议采用**;NetworkX + SQLite 仅适合原型期。
- **构建管线推荐:自研轻量管线**(DeepSeek JSON 输出 + Pydantic 校验 + 嵌入相似度实体消解),重点借鉴 ATOM(原 iText2KG)的**五元组双时间建模**与 Graphiti 的**事实失效不删除**机制。若想少写代码,Graphiti 可整体拿来用(支持 DeepSeek 的 OpenAI 兼容端点,自带 FastAPI 服务),代价是要接受它的 episode 数据模型。

## 二、LLM 驱动的知识图谱构建管线:开源实现盘点

### 2.1 ATOM / iText2KG(AuvaLab)—— 时序建模的最佳参照

仓库:<https://github.com/AuvaLab/itext2kg>(iText2KG 已演进为 ATOM,论文被 EACL 2026 接收,arXiv: [2510.22590](https://arxiv.org/abs/2510.22590))

ATOM 是目前与本项目「演化」需求匹配度最高的开源实现,其 README 描述的三模块并行管线:

1. **原子事实分解**:LLM 把输入文档切成 <400 token 的自包含「原子事实」,缓解长文抽取的遗忘效应(官方声称事实穷尽度 +31%、稳定性 +17%);
2. **原子时序图构建**:从每条原子事实并行抽取**五元组** `(subject, predicate, object, t_start, t_end)`,并做嵌入;
3. **并行原子合并**:两两归并,实体消解用嵌入余弦相似度(默认阈值 θ_E=0.8,关系 θ_R=0.7),**不依赖 LLM 做消解**,因此可并行、可扩展(官方声称延迟比 Graphiti 低 93.8%)。

对本项目最有价值的设计是**双时间建模**:观察时间 `t_obs`(什么时候从数据源看到这条信息)与有效期 `t_start`/`t_end`(能力项什么时候真实生效/失效)分开记录。例如「某岗位 2026-03 的招聘 JD 不再要求 jQuery」应记为该技能边的 `t_end`,而不是新建一条边。这正是「能力项新增/删除/修改」演化事件的标准语义。

其他可借鉴点:实体嵌入按「名称 0.8 + 标签 0.2」加权(区分同名不同类实体);兼容所有 LangChain chat/embedding 模型(DeepSeek 可经 `langchain-openai` 的 `base_url` 直接接入);内置 Neo4j 存储输出。

**局限**:pip 包为学术项目节奏维护(README 标注 Work in Progress),不含检索/服务层,需要自己包 FastAPI。

### 2.2 Graphiti(getzep)—— 增量更新与事实失效的最佳参照

仓库:<https://github.com/getzep/graphiti>(约 3 万 star,Zep 公司的开源核心,论文 arXiv: [2501.13956](https://arxiv.org/abs/2501.13956))

Graphiti 面向「持续演化的时序知识图谱」,README 明确的关键机制:

- **双时序 + 事实失效**:每条事实(边)带有效期窗口;信息变化时旧事实被**标记失效而非删除**,因此天然支持「查询任意历史时点为真的事实」——正是演化回放要的能力;
- **Episode 溯源**:每个实体/关系都能追溯到产生它的原始数据(episode),满足置信度追溯与审计;
- **Schema 可指定可涌现**:通过 Pydantic model 预定义实体/边类型(prescribed ontology),对「岗位—技能」这类强 schema 产品很合适;
- **增量构建**:新数据即时融合,无需批量重算;
- **DeepSeek 兼容**:README 明确支持经 `OpenAIGenericClient` 使用任何 OpenAI 兼容 `/v1` 端点(点名 DeepSeek),但强调依赖**结构化 JSON 输出**的可靠性,提供 `json_schema`/`json_object` 两种模式兜底;
- **自带 FastAPI REST 服务与 docker-compose**(Neo4j / FalkorDB profile),开箱即用。

后端支持 Neo4j 5.26、FalkorDB、Amazon Neptune;**Kuzu 后端已被官方标记 deprecated**(上游停止维护,见 §3.3)。

**局限**:数据模型围绕「episode 摄入」组织,若我们的输入是结构化批数据(招聘 JD 快照、课程大纲),要把它们包装成 episode;检索面向 agent 记忆场景,岗位图谱的分析型查询仍要自己写 Cypher。

### 2.3 Microsoft GraphRAG —— 只借鉴思路,不建议采用

仓库:<https://github.com/microsoft/graphrag>

官方 README 已挂出警告:**项目处于维护模式(largely in maintenance mode),不再接受新 PR、不再开发新功能**,仅做安全修复。且官方自述索引开销昂贵(⚠️ "indexing can be an expensive operation")。其面向静态文档批处理的社区检测 + 社区摘要架构,与我们的增量演化场景不匹配。

可借鉴:其实体/关系抽取 prompt 中让 LLM 同时输出关系强度分数的做法,以及 [Prompt Tuning](https://microsoft.github.io/graphrag/prompt_tuning/overview/) 文档中「用领域样本自动调抽取 prompt」的方法论。

### 2.4 LightRAG(HKUDS)—— 增量删除与存储抽象可借鉴

仓库:<https://github.com/HKUDS/LightRAG>

定位是轻量 GraphRAG 替代,重 RAG 检索、轻图谱产品化,与本项目定位有距离,但两点值得抄:

- **增量更新与选择性删除**:删除文档时利用索引期建立的 LLM cache 快速重建受影响的实体/关系,避免全量重算——我们做「数据源快照替换」时同样需要这种受影响子图重建策略;
- **抽取模型选型经验**:官方明确建议抽取环节用**非思考(non-thinking)模式**的快速模型(在国内点名 DeepSeek 系),思考模型会显著拖慢且加价——对应到我们就是用 `deepseek-chat` 而非 `deepseek-reasoner` 做批量抽取;
- 存储层做了 KV/向量/图/状态四类后端抽象,默认 NetworkX 内存图 + 文件持久化(官方注明**仅适合开发调试**),生产建议 PostgreSQL 一体化或 Neo4j/Memgraph。

### 2.5 Triplex(SciPhi)—— 不适用

模型页:<https://huggingface.co/SciPhi/Triplex>

Phi3-3.8B 微调的本地三元组抽取模型,卖点是替代 GPT-4 抽取以省 98% 成本。但:权重为 **cc-by-nc-sa-4.0**(商用受限,超过 500 万美元营收需授权);需本地 GPU 推理;抽取的是无时间维度的三元组。我们已确定用 DeepSeek API(本身成本低),没有引入本地小模型的必要。

### 2.6 其他

Neo4j Labs 的 [llm-graph-builder](https://github.com/neo4j-labs/llm-graph-builder) 提供「文档 → Neo4j 图谱」的完整 Web 应用参考实现,可作 UI/流程参考;LangChain 的 `LLMGraphTransformer` 与 LlamaIndex 的 `PropertyGraphIndex` 属于通用抽取封装,能力弱于上述专门项目,不展开。

### 2.7 管线四要素的借鉴清单

| 能力 | 借鉴对象 | 具体做法 |
|---|---|---|
| 实体/关系抽取 | ATOM、LightRAG | 文本先切「原子事实」再抽取;用 DeepSeek JSON 输出(`response_format={"type":"json_object"}`)+ Pydantic 校验;抽取用非思考模型 |
| Schema 对齐 | Graphiti、ATOM | 预定义岗位/技能/能力项的 Pydantic 实体与边类型;技能名标准化后,用「名称+标签」加权嵌入 + 余弦相似度(阈值 ≈0.8)对齐到既有节点,不靠 LLM 逐对判断 |
| 增量更新 | Graphiti、ATOM、LightRAG | 新快照只生成「原子图」再与主图合并;变更落为演化事件;删除走「受影响子图重建」而非全图重算 |
| 置信度管理 | GraphRAG、Graphiti | 抽取时让 LLM 输出 0–1 置信分;同一事实被多个数据源/多次快照重复观察时提升权重;每条边保留 `t_obs` 列表与来源引用(episode 思想)做溯源 |

## 三、图存储对比

### 3.1 Neo4j Community Edition —— 推荐

依据:[官方 Operations Manual](https://neo4j.com/docs/operations-manual/current/introduction/)、[数据库管理文档](https://neo4j.com/docs/operations-manual/current/database-administration/)

- **部署重量**:官方 docker 镜像单容器即起,docker-compose 一段配置;JVM 底座,默认堆/页缓存各 512MB,单机跑我们这个量级(数万节点)1–2GB 内存足够。社区版为单实例设计,无集群——正好符合单机约束。
- **许可与限制**:GPLv3 开源(作为独立服务经 Bolt 协议访问,不传染应用代码);**只能有一个用户数据库**、无自定义角色/用户管理、无企业备份工具。对单产品单库场景均无实际影响。
- **Python 生态**:官方 `neo4j` 驱动成熟;是 Graphiti、ATOM、LightRAG、llm-graph-builder 的共同首选后端——选它意味着上层管线随便换/混用都不用动存储。
- **查询能力**:完整 Cypher,含时间类型、路径查询、可选的 APOC 扩展。
- **时间维度建模**:属性图上成熟做法,两层结构即可满足工单要求:
  - 边 `(:岗位)-[:REQUIRES {valid_from, valid_to, confidence, sources}]->(:技能)` 记录有效期(借鉴 Graphiti 失效不删除);
  - `(:EvolutionEvent {type: 新增|删除|修改, at, payload})-[:AFFECTS]->(边/节点)` 记录演化事件,按 `at` 建索引即可支持时间区间查询与逐事件回放。
  - 「某时点图谱快照」= `MATCH ... WHERE r.valid_from <= $t AND ($t < r.valid_to OR r.valid_to IS NULL)`,一条 Cypher 完成。

### 3.2 PostgreSQL + Apache AGE —— 备选

依据:[apache/age 发布页](https://github.com/apache/age/releases)(2026-07 发布 1.8.0,支持 PG13–PG18)

- **部署重量**:PG 扩展形态,若系统本就需要 PostgreSQL(用户、任务、原始 JD 快照等关系数据),则**零新增容器**,还可顺带用 pgvector 存嵌入,一库三用,这是它对本项目唯一但很实在的吸引力。
- **查询能力**:openCypher **子集**。2026 年仍在补齐基础语法:`MERGE ON CREATE/ON MATCH SET`、谓词函数、模式表达式都是 1.8.0 才合入,`FOREACH` 至今未支持([issue #2381](https://github.com/apache/age/issues/2381) 将其列为 Phase 1 兼容性缺口);跨 PG 大版本升级不支持 pg_upgrade,需 dump/restore。
- **Python 生态**:有官方 Python 驱动(psycopg 系),但 Graphiti/ATOM/LightRAG **均不支持 AGE 后端**,上层管线全部要自己写。
- **时间建模**:图查询可与 SQL 混写,演化事件反而可以直接落普通 PG 表,时间查询用 SQL,这点不差。
- 结论:仅当团队强烈希望「只运维一个 PostgreSQL」时选它,并接受 Cypher 缺口与生态孤立。

### 3.3 KuzuDB —— 不建议

依据:[kuzudb/kuzu](https://github.com/kuzudb/kuzu)(已归档)、[Waterloo 官方新闻](https://cs.uwaterloo.ca/news/waterloo-based-graph-database-start-up-kuzu-acquired-apple)、[BetaKit 报道](https://betakit.com/apple-strikes-deal-to-acquire-canadian-database-software-startup-kuzu/)

嵌入式属性图数据库,技术路线(进程内、Cypher、零运维)本来非常契合本项目。但 **Kùzu Inc. 于 2025-10-09 被 Apple 收购,GitHub 仓库次日归档转只读,官网已关停**,最终版 0.11.3 之后不再有修复。Graphiti 已将 Kuzu 后端标记 deprecated 并计划移除。社区虽有 MIT fork,但为一个新项目押注无主上游不值得。

### 3.4 NetworkX + SQLite —— 仅原型期

NetworkX 是纯 Python 内存图库([官方文档](https://networkx.org/documentation/stable/)),数万节点/十万边的规模内存完全装得下,算法库(中心性、社区发现)对图分析还很有用。但:无查询语言(全靠 Python 代码遍历)、无并发访问、持久化需自己序列化到 SQLite/文件、时间维度全手工。LightRAG 把它的 NetworkX 默认存储明确标注为「仅开发调试用」。适合第一周原型验证抽取效果,不适合承载产品。

### 3.5 FalkorDB —— 值得留意的轻量替补

调研 Graphiti 时发现的选项(<https://github.com/FalkorDB/falkordb>):Redis 模块形态的属性图数据库,单容器 `docker run falkordb/falkordb` 即起,支持 openCypher,是 Graphiti 官方支持的两大后端之一。比 Neo4j 轻(无 JVM),但社区、文档与教学资源远少于 Neo4j。若后期嫌 Neo4j 重可平移(Graphiti 层面换后端只改一个 driver)。

### 3.6 对比总表

| 方案 | 部署重量(docker-compose) | Python 生态 | Cypher/查询能力 | 时间建模难易 | 维护风险 |
|---|---|---|---|---|---|
| **Neo4j Community** | 单容器,JVM,约 1–2GB 内存 | 官方驱动 + 所有主流管线首选后端 | 完整 Cypher + APOC | 易:属性有效期 + 事件节点,纯 Cypher 查询 | 低(商业公司,GPLv3 核心持续投入) |
| PG + Apache AGE | 零新增(复用 PG) | 官方驱动,但无管线框架支持 | openCypher 子集,基础语法仍在补齐 | 中:可混用 SQL,事件落普通表 | 中(Apache 项目,迭代偏慢) |
| KuzuDB | 零容器(嵌入式) | pip 即装 | Cypher 方言 | 中 | **高:上游已归档停更** |
| NetworkX + SQLite | 零容器 | 原生 Python | 无查询语言 | 难:全手工 | 低(但能力天花板低) |
| FalkorDB | 单容器,轻量 | Graphiti 官方后端 | openCypher | 同 Neo4j 思路 | 中(社区较小) |

## 四、推荐方案与理由

**图存储:Neo4j Community Edition。** 理由:(1) 规模上万级节点对它是玩具级负载,社区版单库、单实例的全部限制都踩不到;(2) 它是 Graphiti/ATOM/LightRAG 的公共后端,管线选型不被存储绑死;(3) 演化事件的时间建模在完整 Cypher 下最省事;(4) docker-compose 单容器满足部署约束。AGE 的「一库三用」诱惑真实存在,但 Cypher 缺口 + 无管线框架支持,会把省下的一个容器加倍还回开发成本。

**构建管线:自研轻量管线,两个现成项目按模块借鉴。** 我们的输入(招聘 JD、课程数据)是强 schema 的领域数据,不是开放域文档,通用管线的大部分复杂度用不上。建议:

1. 抽取:DeepSeek `deepseek-chat`(非思考模式)+ JSON 输出 + Pydantic schema 校验,按 ATOM 思路先切原子事实再抽五元组 `(岗位, 需要, 技能, t_start, t_end)`;
2. 对齐:技能/能力项嵌入(名称+类型加权)+ 余弦相似度阈值消解,对齐失败的进候审队列;
3. 增量:每次数据快照生成增量子图,与主图合并时产出演化事件(新增/删除/修改),旧边写 `valid_to` 失效而非删除(Graphiti 机制);
4. 置信度:边上维护 `confidence` + 观察次数 + 来源列表,多源重复观察加权提升,低于阈值的边在产品端降权展示。

若想压缩自研工作量,**直接采用 Graphiti + Neo4j** 是可行的次优解(DeepSeek 兼容、自带 FastAPI 服务与双时序机制),代价是接受 episode 摄入模型并在其上做岗位图谱的定制查询;建议先用它跑通一个数据源的端到端 demo,再决定是否换自研。

## 五、关键链接

- ATOM / iText2KG:<https://github.com/AuvaLab/itext2kg> · 论文 <https://arxiv.org/abs/2510.22590>
- Graphiti:<https://github.com/getzep/graphiti> · 论文 <https://arxiv.org/abs/2501.13956>
- Microsoft GraphRAG(维护模式声明见 README):<https://github.com/microsoft/graphrag>
- LightRAG:<https://github.com/HKUDS/LightRAG>
- Triplex:<https://huggingface.co/SciPhi/Triplex>
- Neo4j 社区版/企业版差异:<https://neo4j.com/docs/operations-manual/current/introduction/>
- Apache AGE 发布页:<https://github.com/apache/age/releases>
- KuzuDB 归档仓库:<https://github.com/kuzudb/kuzu> · 收购报道:<https://betakit.com/apple-strikes-deal-to-acquire-canadian-database-software-startup-kuzu/>
- FalkorDB:<https://github.com/FalkorDB/falkordb>
