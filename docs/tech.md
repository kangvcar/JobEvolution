# 技术篇

智演后端怎么搭、数据怎么流、图怎么存、接口怎么开。拿到本文和 [`product.md`](product.md)、根目录 [`CONTEXT.md`](../CONTEXT.md) 就可以开工。页面视觉以原型 [`prototypes/signature-ui.html`](prototypes/signature-ui.html) 为准。

术语只准用 `CONTEXT.md` 里的词。本文只写定案，选型调研原稿不随提交源码分发。

一期不做代码之外的事：不自建学习内容库，不把资源节点写进谱，不上 Kafka，不把采集流墙和演化时间轴做成前端交互。切片差分要做，对照链接要做。

## 运行时

| 件 | 选型 | 干什么 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI | HTTP、采集 worker、抽取、匹配 |
| 前端 | React + Next.js（App Router） | 五个路由，见产品篇 |
| 图 | Neo4j Community，单容器 | 图谱 + 证据引用 + 演化事件 |
| 总线 / 会话 | Redis 7，单容器 | Stream、指纹集合、简历会话、直通开关、资源缓存 |
| LLM | DeepSeek、B.AI 或 Tuzi 的 OpenAI 兼容 API | 所有生成与 JSON 抽取，按 `LLM_PROVIDER` 切换 |
| 嵌入 | 硅基流动 `BAAI/bge-m3`（OpenAI 兼容） | 技能对齐、实体消解、岗位聚类。无 `EMBED_API_KEY` 时回落本地哈希向量，测试与 CI 不出网 |

首个生产环境在单台服务器运行 Docker Compose,由 HTTPS 反向代理统一入口；`web` 与 `api` 同源,默认关闭 CORS,只允许配置中明确列出的可信来源。容器包括 `api`、`web`、`neo4j`、`redis` 和独立每日任务,不拆微服务。评测金标和 JD 快照走仓库文件,不另起 Postgres。管理员一口令,写在环境变量 `ADMIN_PASSWORD`。

```
apps/api/                 FastAPI
  app/main.py
  app/llm/client.py       多供应商 chat，唯一出口
  app/llm/embed.py        bge-m3
  app/collectors/         官方 ATS 招聘门户
  app/pipeline/           抽取、消解、入谱、发现、审核闸
  app/matching/           对齐、匹配分、缺口、学习路径
  app/graph/              Cypher 封装
  app/routers/
apps/web/                 Next.js
data/official-only/jd/    官方 JD 快照原文
data/eval-official-only/  官方金标 JSONL
docker-compose.yml
```

依赖锁在 `apps/api/pyproject.toml` 和 `apps/web/package.json`。新库先过「代码规范」那一节的梯子。

## 总体架构

```
官方 ATS 招聘门户
        │  fingerprint 幂等
        ▼
  data/official-only/jd/{id}.json  +  Redis SET ingest:fp
        │  XADD jobs:events（采集进度，给 worker / 可选管理页）
        ▼
  抽取 worker  ── 配置供应商 JSON ──► Pydantic
        │
        ├─ 技能对齐（词表 → bge 余弦 0.85）
        ├─ 入池：职责段 ∧ 簇内覆盖率 ≥30%
        └─ 置信层 → 待审 或 直通
                │
                ▼
         Neo4j 主图
                │
Next.js  ←──  FastAPI  ←──  简历会话（Redis TTL）
                │
          配置供应商（报告总结、学习资源）
          bge-m3（硅基流动，对齐 / 聚类）
```

求职者路径不碰采集。总览和发现页读库里的聚合计数，不订 SSE 粒子流。

## 图存储

Neo4j Community，官方镜像，堆+页缓存合计约 1–2GB。社区版单库、无自定义角色，正好够。Bolt 访问，驱动用官方 `neo4j`。KuzuDB、Apache AGE、NetworkX 作主存储均排除。FalkorDB 只在以后嫌 JVM 时再换，Cypher 与边上的有效期字段保持可平移。

### 节点

| 标签 | 关键属性 |
|---|---|
| `Domain` | `id` 固定四值：`ai` / `data` / `system` / `iot`，`name` |
| `Job` | `id`，`name`，大典编码，`esco_id`，`onet_id`（三码可空），`status`（candidate / emerging / formed），`level_hint` 不分裂节点 |
| `SkillCategory` | `id`，`name`。只导航，不对账。一期固定桶：语言 / 框架 / 平台 / 工程 / 领域知识 |
| `Skill` | `id`，`name`，同义词列表，`embedding_ref` |
| `Evidence` | `id`，`path`（`data/official-only/jd/...`），`source`（官方 ATS），`company`（规范化公司名，独立源计票用这个），`observed_at`，`simhash` |
| `EvolutionEvent` | `id`，`kind`，`at`，`confidence`，`review`（pending / approved / auto_passed / rejected），`payload` JSON（含 `skill_id`、旧/新边字段） |

预留标签 `Resource`，一期禁止 `CREATE`。学习资源只进 Redis `resource:{skill_id}`。

### 边

```
(:Job)-[:IN_DOMAIN]->(:Domain)
(:Skill)-[:IN_CATEGORY]->(:SkillCategory)
(:Job)-[:REQUIRES {
    kind: "required"|"bonus",          // 必备 / 加分
    proficiency: "aware"|"able"|"expert", // 了解 / 熟练 / 精通
    weight: float,
    levels: ["junior"|"mid"|"senior"],
    valid_from: datetime,
    valid_to: datetime|null,
    confidence: float,
    layer: "high"|"mid"|"low",
    sources: [evidence_id]
}]->(:Skill)
(:EvolutionEvent)-[:AFFECTS]->(:Job)
(:Job)-[:ALIAS_OF]->(:Job)              // 簇判别为别名时
```

Community 版关系不能指向关系。证据只当节点，id 写在 `REQUIRES.sources` 和 `EvolutionEvent.payload`。不要建 `SUPPORTS` / `AFFECTS` 指向 `REQUIRES`。

旧要求边写 `valid_to`，不删。某时点切片：

```
MATCH (j:Job {id:$job})-[r:REQUIRES]->(s:Skill)
WHERE r.valid_from <= $t AND (r.valid_to IS NULL OR $t < r.valid_to)
RETURN j, r, s
```

`EvolutionEvent.at` 建索引。总览流水按 `at` 倒序取边级/节点级事件。时间轴回放等于按序重演这些事件，产品一期不把回放做成页面控件。

冷启动不手录图谱。代码里只写死四个 `Domain`，以及 [`product.md`](product.md) 的 17 个规范岗位名当对齐靶子。`Job` / `Skill` / `REQUIRES` / 岗位状态由管线从 JD 写入。大典编码、`esco_id`、`onet_id` 可空，ESCO / O\*NET / 大典只作对照。公司名用规则规范化（去「有限公司 / 股份 / 括号地名」），计独立源只认 `Evidence.company`；不要先手写全量别名表。

## 数据采集

分层：`source` 产出原始记录，`controller` 去重与落盘，`sink` 写 Redis Stream。不要去 pip 装那些已失效的 Scrapy 站群。

**冷启动。** 官方招聘门户是唯一主数据源。各门户先映射到统一记录：公司、岗位名、正文、发布日、渠道。缺正文的行丢掉。标题用领域词粗滤四领域（人工智能优先），去近重后写入 `data/official-only/jd/`，再跑抽取。不要手写赛题 JD，不要先灌 `bootstrap.py`。天池人岗匹配只补条数或字段缺口。

**主力增量。** Greenhouse / Lever / Ashby 公开 JSON；NCSS 公开列表。低频、字段稳。不挡冷启动。

**增量源。** BOSS / 猎聘 / 智联走 Playwright 已登录会话 + `wait_for_response` 拦 JSON（BOSS：`joblist.json`）。`headless=False` 或持久化 user data dir。主账号会封，文档里写清用小号。合规用户已明示忽略。

**幂等。** `fingerprint = sha256(source + job_id)`，没有站点 ID 时用 `规范化(公司|标题|城市)`。命中 Redis `ingest:fp` 则跳过。正文另算 64-bit simhash，Hamming ≤3 视为近重：只留 `observed_at` 最早的一条作证据，其余不计独立源。

**事件。** 每入库一条 JD、每抽完一簇，`XADD jobs:events`。字段：`id`、`type`（`collect_started` / `jd_ingested` / `collect_portal_failed` / `collect_finished` / `cluster_ready` / `review_enqueued` / `job_promoted`）、`payload`。SSE `GET /events/stream` 需管理会话，求职者页面不接。

## 图谱构建与幻觉防控

输入是强 schema 的 JD，不套 Graphiti 整包。自研短管线，机制抄 ATOM 的双时间和 Graphiti 的失效不删。抽取使用配置的非思考模型。

1. **切段。** 职责、要求、福利、公司介绍分开。技能只允许从职责/要求段出。福利和介绍里出现的词不算入池。
2. **抽取。** DeepSeek JSON，Pydantic 校验。一条 JD 抽出：岗位名、领域、原子技能点列表（各带明确必备/明确加分/未标、熟练级、置信 0–1、原文摘录）。只有原文明确写"必须"、"要求"、"熟练掌握"或列入清晰任职要求时才记明确必备,写"优先"、"加分"时记明确加分,其余提及一律未标。斜杠连接的复合技术表述拆开；原文明确写"任选"、"或"或"至少两种"时同时抽要求组和 `min_required`。沟通、团队协作、学习能力等通用素质丢弃。模型品牌从同句动作抽 API 集成、部署、微调或评测,品牌保留在摘录；没有动作只记观测中。校验失败整单重试一次，再失败进待审并标抽取失败。
3. **消解。** 图谱最初没有技能词表。抽出的技能字符串用 bge 聚类（阈值 0.85），簇心写成 `Skill`。对齐先统一大小写、全半角、空格与明确标点差异,再查已获批同义词,最后才走余弦；这套 `align_skill(text) -> Skill | None` 与匹配侧共用。跨语言、缩写与全称只生成技能合并提案,人工比较定义与原文后才能写入同义词表并建立旧 ID 映射；嵌入相近不能自动合并,LangChain/LangGraph、GPT/Gemini、RAG/向量数据库等相关技术保持独立。岗位名对齐 17 个靶子，阈值可单独 0.80；对不上进发现簇。对不上任何 `Skill` 的新串进待审。只有多个独立源明确要求同一品牌且达到入池门槛时,该品牌才可单独成技能点。
4. **入池。** 该技能点在岗位去重 JD 簇里的簇内覆盖率 ≥30% 才写 `REQUIRES`。要求组按每份 JD 是否出现至少 `min_required` 个组员计算组合覆盖率。多份 JD 中的技能只有支撑同一岗位职责、单份 JD 内很少共同出现且组合覆盖率 ≥30% 时才生成要求组合并提案,人工批准前不写要求组。技能类目相同不是替代证据。低于门槛的技能记观测中：只挂在岗位节点 `watching[]`，不写要求边，诊断报告里写明不是缺口。
5. **必备/加分。** 覆盖率达标后,按独立源汇总要求判定票。未标票不进性质判定的分母,但与另外两类票数一起展示。明确必备票或明确加分票占已分类票至少 60%,且对应票来自至少两个独立源,才写相应 `kind`;两边都不满足时只生成审核提案,不写正式要求边。人工决定保留三类票数、原文与决定理由,后续周期仍按新证据重算。
6. **要求组对账。** 同一证据形成的组员要求由要求组替代,匹配与缺口集只按 `min_required` 计算。只有不同证据指向另一项独立职责时,组员技能点才能同时保留单独要求边。
7. **置信层。** 按优先级：无证据链 → 低；≥3 独立源且抽取置信 ≥0.8 → 高；抽取置信 ≥0.5 → 中；其余 → 低。高：直通开着时可自动过，关着也进待审。中待审，直通开启则入谱，边上 `layer=mid`，UI 标「待更多证据」。低永不自动入谱，管理员仍可批。直通开关跳过的是人批，不是证据底线。
8. **合并。** 新快照只生成增量子图。与主图比较产出演化事件：要求边新增 / 移除（写 `valid_to`）/ 修改（旧边失效 + 新边）。既有岗「显著变化」：覆盖率从 <15% 跨过 30%。按 `observed_at` 切年或切周期，不要手写演化事件。删除数据源时只重建受影响岗位子图。技能类目：入池后的技能点归进固定桶，不手录类目树。
9. **待审。** 新岗位首次发布、核心必备新增、低置信抽取、消解失败，都进同一队列。管理员批/改/驳。直通默认关，开了只对中高置信记 `auto_passed`。低置信批了记 `approved`，不记 `auto_passed`。队列实体就是 `EvolutionEvent` 且 `review=pending`。

公开发布前对每个可诊断岗位跑确定性诊断发布校验:岗位定义非空,至少一组有效必备要求,每条有效要求有未撤回证据,同一规范技能点没有重复有效要求,且没有尚未处理的岗位要求异常。要求等价数按独立要求边计 1、要求组计 `min_required`;必备上限 12,全部正式要求上限 24。相对上一发布版本,新增必备超过 `max(3,上期必备要求等价数 × 50%)`,或新增正式要求超过 `max(5,上期正式要求等价数 × 50%)`,即暂停该岗位发布；首个版本只检查数量上限。管理员修正后重跑,或提交带理由的人工放行决定。校验失败只把该岗位排除出推荐与诊断,不阻断同版本内其他岗位；不足三个推荐时返回实际数量。这里不增加单岗位 F1、全部人工复核或清空待审提案门槛。

LLM 输出必须带摘录。写边时把摘录对应的 `Evidence.id` 放进 `REQUIRES.sources`。没有摘录的边视为无证据链，层=低。

## 新岗位发现

与能力更新同一管线的另一个出口，闸相同。

1. 对近期未对齐到既有岗位的 JD，用「标题 + 已抽出技能点名」拼字符串做 bge 嵌入，聚类。一期 sklearn Agglomerative（最小簇 3 条）。不要为演示装 HDBSCAN，也不要用种子跳过聚类。
2. DeepSeek 只打簇代表，三分类：新岗位 / 既有别名 / 噪声。别名写 `ALIAS_OF` 并入已有岗。源节点可留着挂边，不用 `candidate` 冒充漏斗。噪声丢弃。新词或技能爆发只加簇置信，不当主判据。
3. 状态机，阈值做成常量（`pipeline/constants.py`），改一处即可：
   - 候选：未入谱，`Job.status=candidate`。发现页可展示；`GET /jobs`、`GET /jobs/{id}`、`GET /graph/jobs/{id}`、`POST /diagnose` 无口令时对 candidate 404 / 400
   - 萌芽：≥3 独立源、90 天窗、LLM 判为新岗位。入谱，标新兴
   - 成型：(`≥10` 独立源 或 持续 `≥6` 个月) 并且 岗位定义曾 `approved` 或 `auto_passed`
4. 独立源 = 规范化后的 `Evidence.company`。simhash 近重的正文不计票。渠道名（Greenhouse、NCSS）不计票。

首批覆盖名单见 [`product.md`](product.md)。技术上四领域都有 `Domain` 节点；演示深度优先 `ai`。萌芽/成型一律由独立源计票，缺证据的岗停在候选，不要手补 `status`。赛题那一对须跑管线：Agent 工程师从 ≥3 独立源 JD 入萌芽；大模型应用工程师从旧年快照 + 新年 JD 写出能力变更（覆盖率跨过 30% 的技能入池，不再出现的写 `valid_to`）；「大模型应用开发工程师」由簇判别写 `ALIAS_OF`。

## 匹配与差距分析

### 简历

PDF：`pdfplumber` 取文本层。`.docx`：`python-docx`。支持中英文混排；`.doc`、图片和扫描件直接 400，提示不支持。不要上 OCR、LibreOffice 或 pyresparser。

配置的 JSON 模型拆两个子任务并行：基本信息+教育+经历；技能点列表（引导词表用当前图谱技能名）。输出过 `align_skill`。首次诊断前可修改技能点与明确的熟练级,修改只写当前会话。会话结果进不持久化的 Redis，TTL 1 小时，key `session:{id}`；Redis 重启后提示重新上传。字段级 F1 另报，不进三项准确率。

上传前页面必须告知必要简历文本会发送给当前配置的模型服务商,产品数据库不保存简历,匿名会话最长保留一小时。选择文件或拖放即表示确认本次处理范围,不增加单独 checkbox。原文件仍按 ADR-0032 在解析完成或失败后立即删除；服务商没有经合同和配置验证的数据承诺时,页面不得写"绝不留存"。

双栏版式掉点时再引入 SmartResume 版面重建。一期不做。

### 对齐与匹配分

`align_skill` 唯一入口。评测时把阈值冻在配置快照里，不许随手改。

匹配分只在服务端算，产品页展示档位，不把 0–100 做成大数字：

```
score = 100 * (req_cover + 0.3 * bonus_cover) / (req_full + 0.3 * bonus_full)
```

分母为 0 则 `score = 0`。边上的 `weight` 不进分，当 1。必备未覆盖记 0；简历标了熟练级且低于岗位要求记 0.5（半档，进缺口集）。加分缺失不伤必备。简历没标熟练级则只比有无，不算半档。经验年限、学历旁注，不进分。

档位切分写在 `matching/bands.py`，与原型同一组阈值（匹配分先除以 100 再比）：≥0.85 高度匹配，≥0.60 基本匹配，≥0.35 有明显差距，其余不匹配。改文案或阈值只改这一处。换档条件也写在这里：`shift_set(job, skills)` 对缺口与半档做最小补集，使档位升一档。学习路径读这个集合。

缺口集 = 目标岗必备技能点里，对齐后未覆盖或半档不足的集合。三项准确率的匹配项拿缺口集 F1，喂金标简历技能 × 金标岗位要求，不喂解析输出。口径见 `CONTEXT.md`。

### 学习路径

按换档条件排序，默认最多 5 步。先列入能单独换档的技能点，再列入成对才能换档的，其余缺口与半档补齐。每步：`skill_id`、职责段摘录、一条 URL、`why`（换档 / 半档 / 缺口）。资源现查 DeepSeek，缓存 Redis 7 天，key `resource:{skill_id}`。赛题那一对可把课表 URL 预置进同一缓存，禁止 `CREATE` `Resource` 节点。抽检换档条件上的技能点是否都有一条可打开的链接。不定准确率。

对照链接：打开 `/diagnose?session_id=&job_id=` 且 `session:{id}` 未过期时，前端直接 `POST /diagnose`。过期回 idle。不另做历史表。

## API

JSON，UTF-8。错误体 `{ "error": str, "detail": str | null }`。管理口令只交给登录接口做常量时间比较；成功后签发 Redis 短期会话，浏览器只保存 `Secure`、`HttpOnly`、`SameSite=Strict` Cookie。管理写请求校验 CSRF，登录限速。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/meta` | 四领域、演示统计。直通开关只在管理路由返回 |
| GET | `/jobs` | 列表。query：`domain`，`status`，`q`。无口令丢掉 `candidate`；`status=candidate` 无口令返回空列表 |
| GET | `/jobs/{id}` | 获批定义、典型职责、独立源数、岗位更新时间、数据状态、相近岗位和证据摘要。candidate 无口令 404 |
| GET | `/graph/jobs/{id}` | 当前与上一周期、类目、按必备 / 加分 / 观测中分组的技能点、`REQUIRES` 判定摘要与票数、`period_delta` 文字清单。candidate 404 |
| POST | `/sessions` | multipart 简历 → `{session_id, skills, preview_text}` |
| PUT | `/sessions/{id}/skills` | 会话内修正技能点与明确熟练级 |
| POST | `/diagnose` | `{session_id, job_id, levels?}` → 对照报告。含换档条件与按此排序的学习路径、邻近岗档位。`job_id` 为 candidate 时 400。前端可用 query `session_id` + `job_id` 自动再 POST |
| POST | `/diagnose/simulate` | `{session_id, job_ids, assumed_skill_ids, watching_skill_ids?}` → 两个对照岗位与邻近岗位的假设档位和换档条件。不写会话技能或简历证据 |
| GET | `/discover` | 候选 / 萌芽 / 成型看板。有 `ALIAS_OF` 出边的岗不进候选列 |
| GET | `/discover/{id}` | 卷宗：形成原因、去重公司、近期要求、相近岗位差异、市场关注建议、证据与事件。候选也可以 |
| GET | `/feed` | 故事、萌芽/谱内计数、管线、热度、流水。候选簇不计别名。总览第一屏只用故事和计数；管线/热度/流水给发现页和总览 `<details>` |
| POST | `/admin/session` | 校验共享口令并签发短期管理会话 |
| DELETE | `/admin/session` | 注销当前管理会话 |
| GET | `/admin/queue` | 待审 `EvolutionEvent` |
| POST | `/admin/queue/{id}/approve` | body 可带改写后的 payload |
| POST | `/admin/queue/{id}/reject` | |
| POST | `/admin/jobs/{job_id}/versions/{version_id}/approve-all` | 批准该岗位版本全部待审提案；岗位要求异常须带 `override_reason`,其他确定性校验不可跳过 |
| GET | `/admin/passthrough` | `{enabled: bool}`。管理页画 `aria-pressed` |
| PUT | `/admin/passthrough` | `{enabled: bool}` |
| GET | `/events/stream` | SSE，管理可选。`Last-Event-ID` 从 Redis Stream 续 |

`/diagnose` 同步返回完整报告，前端 run 态自己播等待动画。报告字段覆盖方向结论、是否无法区分、简历定位判断、优势与风险、简历内容状态、岗位关键词对照、双轨行动清单、项目证据提示、求职叙事稿、简历证据地图关系、邻近岗位迁移数据、市场信号和判断依据。引用已有事实的模型判断携带简历证据片段 ID；缺失判断携带被检查的简历部分,原文没有的事实只进入待补字段。匹配档位、必备覆盖、有证据的岗位专属技能数、可迁移工程能力数和最小换档要求等价数全部相同时返回无法区分及各自换档条件；数据新鲜度与岗位证据量只影响展示顺序。学习路径按换档条件排序。匹配分可放在 payload 里给档位函数用，UI 不直接渲染该数字。

批量批准先解析岗位版本的全部待审提案,再运行证据 ID 存在、未撤回、摘录存在、无重复有效要求和岗位定义非空检查。任一检查失败时整批不写决定。岗位要求异常可以通过非空 `override_reason` 放行。成功时为每项写审核决定并关联同一个批量决定 ID,审计 actor 记录共享管理员会话而非个人身份；不调用独立审核模型。

复制链接与行动清单使用浏览器 Clipboard API,打印与保存 PDF 使用打印样式。后端不生成报告文件,不为导出延长会话 TTL。

换档模拟复用服务端现有匹配与 `shift_set` 逻辑,只把属于缺口、熟练级不足或要求组候选的 `assumed_skill_ids` 合并进本次计算输入。`watching_skill_ids` 只回显到市场观察栏,匹配函数不读取。响应给每个岗位返回原档位、假设档位和新的换档条件,不写 Redis 会话。简历证据地图与邻近岗位迁移地图只消费 `/diagnose` 已有证据关系和最多三个岗位结果,不新增图数据库实体。

图谱前端用 AntV G6 画这一岗的切片，默认 Canvas。切 WebGL 仅当单岗节点明显卡顿。不用 Timebar，不在边上发采集粒子。

## LLM 供应商集成

`app/llm/client.py` 是唯一的生成模型出口。其它模块只依赖 `complete_json(messages) -> dict`，通过 `LLM_PROVIDER` 在 DeepSeek、B.AI 和 Tuzi 的 OpenAI 兼容端点之间切换。B.AI 的 Chat Completions 地址是 `https://api.b.ai/v1/chat/completions`，Tuzi 的地址是 `https://api.tu-zi.com/v1/chat/completions`，认证分别使用对应的环境变量 Bearer Token。

默认 DeepSeek：

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY     必填
DEEPSEEK_BASE_URL    默认 https://api.deepseek.com
DEEPSEEK_MODEL       默认 deepseek-v4-flash
```

B.AI 免费模型评测配置：

```
LLM_PROVIDER=bai
BAI_API_KEY          必填，不写入仓库
BAI_BASE_URL         默认 https://api.b.ai/v1
BAI_MODEL            默认 deepseek-v4-flash-vision-exp
BAI_DISABLE_THINKING 默认 1，B.AI 端点接受时关闭思考以降低延迟；兼容性异常时设为 0
```

Tuzi GPT-5.6 Luna：

```
LLM_PROVIDER=tuzi
TUZI_API_KEY          必填，不写入仓库
TUZI_BASE_URL         默认 https://api.tu-zi.com/v1
TUZI_MODEL            默认 gpt-5.6-luna
TUZI_REASONING_EFFORT 默认 none，降低长文本评测延迟；兼容性异常时可设为 low 或留空
```

调用约定：

- OpenAI SDK，`base_url` 按供应商配置。B.AI 和 Tuzi 使用 OpenAI 兼容 Chat Completions 协议。
- 抽取、簇判别、简历 JSON：DeepSeek 发送 `thinking: {"type": "disabled"}`；B.AI 默认通过 `BAI_DISABLE_THINKING=1` 发送同一关闭提示，若供应商版本不兼容可设为 0；Tuzi 默认发送 `reasoning_effort=none`，可用 `TUZI_REASONING_EFFORT` 调节。三者都使用 `response_format: {"type": "json_object"}`。
- 诊断总结、学习资源：同一配置供应商，仍使用非思考模型；超时 60s，默认 `LLM_MAX_OUTPUT_TOKENS=4096`，失败重试一次；若首个 JSON 截断，第二次追加紧凑输出约束并将输出上限减半。
- JSON 对不上 Pydantic 算失败。
- 外部模型设置全局每日调用量与费用上限,并保留公开接口的每 IP 限速；额度耗尽时明确失败,不在请求中途静默切换供应商。
- 禁止在业务里直接 `openai.OpenAI(...)`。测抽取时 mock `complete_json`。

结构化日志保留 14 天,记录请求 ID、路由、状态码、耗时、模型、Token、费用、管线版本和错误类型；不得记录简历正文、管理员口令、Cookie 或完整会话 ID。每日版本化 JSON 复制到服务器外并保留 30 天,恢复只走幂等导入器。管线失败、连续 48 小时数据陈旧、备份失败和图谱发布失败统一发到一个可配置 Webhook,管理页同时显示最近运行状态。

嵌入在 `app/llm/embed.py`：`embed(texts: list[str]) -> list[list[float]]`。设了 `EMBED_API_KEY` 走硅基流动 `BAAI/bge-m3`（OpenAI 兼容端点，失败即抛，不悄悄降级）；没设走本地字符 3-gram 哈希向量，纯词面匹配，只给测试与 CI 用。这不是 LLM 调用，不走 DeepSeek。

## 代码规范

实现本仓库时按下面做。写多了的删掉再合。

1. 先读本文、`CONTEXT.md`、`product.md`，再创建文件。词与产品篇冲突时改代码，不改着玩术语。
2. 梯子：需要吗 → 仓库里有没有 → stdlib → 已装依赖 → 一行 → 才写新代码。新 pip/npm 要在 PR 里写清梯子哪一档不够。
3. 不要引入已排除项：KuzuDB、Kafka、GraphRAG 整包、Graphiti 当主存储、pyresparser、cytoscape/sigma 作图谱主体、Lightcast API、账户体系。
4. 信任边界：上传 MIME 与大小、口令、LLM JSON（Pydantic）、Cypher 参数化。文件写在 `data/` 下，路径不允许 `..`。
5. 非平凡逻辑留一个可跑检查：`tests/test_*.py` 里一个函数，或模块 `if __name__` 的 assert。三项准确率的回归放 `data/eval-official-only/`，阈值冻结。
6. 共享函数改一处。`align_skill`、置信层、状态机升级、匹配分，禁止每个路由复制一份。
7. 刻意简化写 `# ponytail: <天花板>，<何时升级>`。例如全局一把锁、HDBSCAN 换成更重的聚类。
8. 一次改动只碰任务需要的文件。顺手重构旁边的模块不算完成。
9. 单测覆盖率目标 ≥60% 是赛题硬指标，优先盖 `pipeline/` 与 `matching/`，路由烟测即可。

不要把调研段落粘进代码注释。
