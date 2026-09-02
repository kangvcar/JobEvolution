# 技术篇

智演后端怎么搭、数据怎么流、图怎么存、接口怎么开。拿到本文和 [`product.md`](product.md)、根目录 [`CONTEXT.md`](../CONTEXT.md) 就可以开工。页面视觉以原型 [`prototypes/signature-ui.html`](prototypes/signature-ui.html) 为准。

术语只准用 `CONTEXT.md` 里的词。选型理由在 `docs/research/`，本文只写定案。

一期不做代码之外的事：不自建学习内容库，不把资源节点写进谱，不上 Kafka，不把采集流墙和演化时间轴做成前端交互。切片差分要做，对照链接要做。

## 运行时

| 件 | 选型 | 干什么 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI | HTTP、采集 worker、抽取、匹配 |
| 前端 | React + Next.js（App Router） | 五个路由，见产品篇 |
| 图 | Neo4j Community，单容器 | 图谱 + 证据引用 + 演化事件 |
| 总线 / 会话 | Redis 7，单容器 | Stream、指纹集合、简历会话、直通开关、资源缓存 |
| LLM | DeepSeek 官方 API | 所有生成与 JSON 抽取 |
| 嵌入 | 硅基流动 `BAAI/bge-m3`（OpenAI 兼容） | 技能对齐、实体消解、岗位聚类。无 `EMBED_API_KEY` 时回落本地哈希向量，测试与 CI 不出网 |

首个生产环境在单台服务器运行 Docker Compose,由 HTTPS 反向代理统一入口；`web` 与 `api` 同源,默认关闭 CORS,只允许配置中明确列出的可信来源。容器包括 `api`、`web`、`neo4j`、`redis` 和独立每日任务,不拆微服务。评测金标和 JD 快照走仓库文件,不另起 Postgres。管理员一口令,写在环境变量 `ADMIN_PASSWORD`。

```
apps/api/                 FastAPI
  app/main.py
  app/llm/client.py       DeepSeek chat，唯一出口
  app/llm/embed.py        bge-m3
  app/collectors/         data/本地表 / ATS / NCSS / Playwright
  app/pipeline/           抽取、消解、入谱、发现、审核闸
  app/matching/           对齐、匹配分、缺口、学习路径
  app/graph/              Cypher 封装
  app/routers/
apps/web/                 Next.js
data/jd/                  JD 快照原文
data/eval/                金标 JSONL
docker-compose.yml
```

依赖锁在 `apps/api/pyproject.toml` 和 `apps/web/package.json`。新库先过「代码规范」那一节的梯子。

## 总体架构

```
data/本地表 / ATS / NCSS / Playwright
        │  fingerprint 幂等
        ▼
  data/jd/{id}.json  +  Redis SET ingest:fp
        │  XADD jobs:events（采集进度，给 worker / 可选管理页）
        ▼
  抽取 worker  ── DeepSeek JSON ──► Pydantic
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
          DeepSeek（报告总结、学习资源）
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
| `Evidence` | `id`，`path`（`data/jd/...`），`source`（渠道：local / ats / ncss / tianchi / playwright），`company`（规范化公司名，独立源计票用这个），`observed_at`，`simhash` |
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

分层：`source` 产出原始记录，`controller` 去重与落盘，`sink` 写 Redis Stream。参考结构见 [`research/jd-collection.md`](research/jd-collection.md)，不要去 pip 装那些已失效的 Scrapy 站群。

**冷启动。** 仓库 `data/` 下所有本地 JD 表（CSV / 日后新丢进来的表都算），不限定智联或某一个文件名。各表字段名不同，`source` 先映射到统一记录：公司、岗位名、正文、发布日、渠道。缺正文的行丢掉。标题用领域词粗滤四领域（人工智能优先），去近重后写入 `data/jd/`，再跑抽取。不要手写赛题 JD，不要先灌 `bootstrap.py`。天池人岗匹配只补条数或字段缺口。

**主力增量。** Greenhouse / Lever / Ashby 公开 JSON；NCSS 公开列表。低频、字段稳。不挡冷启动。

**增量源。** BOSS / 猎聘 / 智联走 Playwright 已登录会话 + `wait_for_response` 拦 JSON（BOSS：`joblist.json`）。`headless=False` 或持久化 user data dir。主账号会封，文档里写清用小号。合规用户已明示忽略。

**幂等。** `fingerprint = sha256(source + job_id)`，没有站点 ID 时用 `规范化(公司|标题|城市)`。命中 Redis `ingest:fp` 则跳过。正文另算 64-bit simhash，Hamming ≤3 视为近重：只留 `observed_at` 最早的一条作证据，其余不计独立源。

**事件。** 每入库一条 JD、每抽完一簇，`XADD jobs:events`。字段：`id`、`type`（`jd_ingested` / `cluster_ready` / `review_enqueued` / `job_promoted`）、`payload`。SSE `GET /events/stream` 给管理页可选订阅，求职者页面不接。

## 图谱构建与幻觉防控

输入是强 schema 的 JD，不套 Graphiti 整包。自研短管线，机制抄 ATOM 的双时间和 Graphiti 的失效不删。抽取用非思考模型，见 DeepSeek 一节。

1. **切段。** 职责、要求、福利、公司介绍分开。技能只允许从职责/要求段出。福利和介绍里出现的词不算入池。
2. **抽取。** DeepSeek JSON，Pydantic 校验。一条 JD 抽出：岗位名、领域、技能点列表（各带必备/加分、熟练级、置信 0–1、原文摘录）。校验失败整单重试一次，再失败进待审并标抽取失败。
3. **消解。** 图谱最初没有技能词表。抽出的技能字符串用 bge 聚类（阈值 0.85），簇心写成 `Skill`，簇内原文进同义词。之后 `align_skill(text) -> Skill | None` 先查同义词再余弦，与匹配侧同一函数。岗位名对齐 17 个靶子，阈值可单独 0.80；对不上进发现簇。对不上任何 `Skill` 的新串进待审，不让 LLM 逐对决定。
4. **入池。** 该技能点在岗位去重 JD 簇里的簇内覆盖率 ≥30% 才写 `REQUIRES`。低于此记观测中：只挂在岗位节点 `watching[]`，不写要求边，诊断报告里写明不是缺口。
5. **必备/加分。** 覆盖率达标后，抽取出的 `kind` 与簇内多数票合并；平票标中置信进待审。
6. **置信层。** 按优先级：无证据链 → 低；≥3 独立源且抽取置信 ≥0.8 → 高；抽取置信 ≥0.5 → 中；其余 → 低。高：直通开着时可自动过，关着也进待审。中待审，直通开启则入谱，边上 `layer=mid`，UI 标「待更多证据」。低永不自动入谱，管理员仍可批。直通开关跳过的是人批，不是证据底线。
7. **合并。** 新快照只生成增量子图。与主图比较产出演化事件：要求边新增 / 移除（写 `valid_to`）/ 修改（旧边失效 + 新边）。既有岗「显著变化」：覆盖率从 <15% 跨过 30%。按 `observed_at` 切年或切周期，不要手写演化事件。删除数据源时只重建受影响岗位子图。技能类目：入池后的技能点归进固定桶，不手录类目树。
8. **待审。** 新岗位首次发布、核心必备新增、低置信抽取、消解失败，都进同一队列。管理员批/改/驳。直通默认关，开了只对中高置信记 `auto_passed`。低置信批了记 `approved`，不记 `auto_passed`。队列实体就是 `EvolutionEvent` 且 `review=pending`。

公开发布前对每个可诊断岗位跑确定性诊断发布校验:岗位定义非空,至少一组有效必备要求,每条有效要求有未撤回证据,同一规范技能点没有重复有效要求。失败只把该岗位排除出推荐与诊断,不阻断同版本内其他岗位；不足三个推荐时返回实际数量。这里不增加单岗位 F1、全部人工复核或清空待审提案门槛。

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

DeepSeek JSON 拆两个子任务并行：基本信息+教育+经历；技能点列表（引导词表用当前图谱技能名）。输出过 `align_skill`。首次诊断前可修改技能点与明确的熟练级,修改只写当前会话。会话结果进不持久化的 Redis，TTL 1 小时，key `session:{id}`；Redis 重启后提示重新上传。字段级 F1 另报，不进三项准确率。

双栏版式掉点时再引入 SmartResume 版面重建，见 [`research/resume-parsing.md`](research/resume-parsing.md)。一期不做。

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
| GET | `/jobs/{id}` | 定义、独立源数、技能点表、证据摘要。candidate 无口令 404 |
| GET | `/graph/jobs/{id}` | 当前岗切片：类目、技能点、`REQUIRES`（按 `levels` 过滤）、`period_delta`（`added` / `expired`）。expired 是本周期已写 `valid_to` 的边，给切片差分挂「本周期失效」。candidate 404 |
| POST | `/sessions` | multipart 简历 → `{session_id, skills, preview_text}` |
| PUT | `/sessions/{id}/skills` | 会话内修正技能点与明确熟练级 |
| POST | `/diagnose` | `{session_id, job_id, levels?}` → 对照报告。含换档条件与按此排序的学习路径、邻近岗档位。`job_id` 为 candidate 时 400。前端可用 query `session_id` + `job_id` 自动再 POST |
| GET | `/discover` | 候选 / 萌芽 / 成型看板。有 `ALIAS_OF` 出边的岗不进候选列 |
| GET | `/discover/{id}` | 卷宗：簇、独立源、证据、事件。候选也可以 |
| GET | `/feed` | 故事、萌芽/谱内计数、管线、热度、流水。候选簇不计别名。总览第一屏只用故事和计数；管线/热度/流水给发现页和总览 `<details>` |
| POST | `/admin/session` | 校验共享口令并签发短期管理会话 |
| DELETE | `/admin/session` | 注销当前管理会话 |
| GET | `/admin/queue` | 待审 `EvolutionEvent` |
| POST | `/admin/queue/{id}/approve` | body 可带改写后的 payload |
| POST | `/admin/queue/{id}/reject` | |
| GET | `/admin/passthrough` | `{enabled: bool}`。管理页画 `aria-pressed` |
| PUT | `/admin/passthrough` | `{enabled: bool}` |
| GET | `/events/stream` | SSE，管理可选。`Last-Event-ID` 从 Redis Stream 续 |

`/diagnose` 同步返回完整报告，前端 run 态自己播等待动画。报告字段与产品篇四组一一对应：判断、定位、行动、解释。学习路径按换档条件排序。匹配分可放在 payload 里给档位函数用，UI 不直接渲染该数字。

图谱前端用 AntV G6 画这一岗的切片，默认 Canvas。切 WebGL 仅当单岗节点明显卡顿。不用 Timebar，不在边上发采集粒子。

## DeepSeek 集成

`app/llm/client.py` 是唯一打 DeepSeek 的地方。其它模块只依赖 `complete_json(messages) -> dict`（内部对传输错误重试一次）。

```
DEEPSEEK_API_KEY     必填
DEEPSEEK_BASE_URL    默认 https://api.deepseek.com
DEEPSEEK_MODEL       默认 deepseek-v4-flash
```

调用约定：

- OpenAI SDK，`base_url` 指到官方。
- 抽取、簇判别、简历 JSON：`thinking: {"type": "disabled"}`，`response_format: {"type": "json_object"}`。思考模式会拖慢批量抽取。
- 诊断总结、学习资源：同样非思考；需要稍长文案时仍用 flash，不上 pro，除非 flash 连续失败。
- 超时 60s，失败重试一次。JSON 对不上 Pydantic 算失败。
- 外部模型设置全局每日调用量与费用上限,并保留公开接口的每 IP 限速；额度耗尽时明确失败,不切换到其他模型。
- 禁止在业务里直接 `openai.OpenAI(...)`。测抽取时 mock `complete_json`。

结构化日志保留 14 天,记录请求 ID、路由、状态码、耗时、模型、Token、费用、管线版本和错误类型；不得记录简历正文、管理员口令、Cookie 或完整会话 ID。每日版本化 JSON 复制到服务器外并保留 30 天,恢复只走幂等导入器。管线失败、连续 48 小时数据陈旧、备份失败和图谱发布失败统一发到一个可配置 Webhook,管理页同时显示最近运行状态。

嵌入在 `app/llm/embed.py`：`embed(texts: list[str]) -> list[list[float]]`。设了 `EMBED_API_KEY` 走硅基流动 `BAAI/bge-m3`（OpenAI 兼容端点，失败即抛，不悄悄降级）；没设走本地字符 3-gram 哈希向量，纯词面匹配，只给测试与 CI 用。这不是 LLM 调用，不走 DeepSeek。

## 代码规范

实现本仓库时按下面做。写多了的删掉再合。

1. 先读本文、`CONTEXT.md`、`product.md`，再创建文件。词与产品篇冲突时改代码，不改着玩术语。
2. 梯子：需要吗 → 仓库里有没有 → stdlib → 已装依赖 → 一行 → 才写新代码。新 pip/npm 要在 PR 里写清梯子哪一档不够。
3. 不要引入已排除项：KuzuDB、Kafka、GraphRAG 整包、Graphiti 当主存储、pyresparser、cytoscape/sigma 作图谱主体、Lightcast API、账户体系。
4. 信任边界：上传 MIME 与大小、口令、LLM JSON（Pydantic）、Cypher 参数化。文件写在 `data/` 下，路径不允许 `..`。
5. 非平凡逻辑留一个可跑检查：`tests/test_*.py` 里一个函数，或模块 `if __name__` 的 assert。三项准确率的回归放 `data/eval/`，阈值冻结。
6. 共享函数改一处。`align_skill`、置信层、状态机升级、匹配分，禁止每个路由复制一份。
7. 刻意简化写 `# ponytail: <天花板>，<何时升级>`。例如全局一把锁、HDBSCAN 换成更重的聚类。
8. 一次改动只碰任务需要的文件。顺手重构旁边的模块不算完成。
9. 单测覆盖率目标 ≥60% 是赛题硬指标，优先盖 `pipeline/` 与 `matching/`，路由烟测即可。

调研原文与竞品链接留在 `docs/research/`，实现时按需打开，不要把调研段落粘进代码注释。
