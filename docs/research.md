# 开源借鉴指南

实现时先看这张表，再决定 pip/npm 还是自己写。理由和出处在 `docs/research/` 调研里，本文不复述。那些篇是档案：文首仍可能写暗色大屏、Timebar、Graphiti 次优解，定案以 [`product.md`](product.md)、[`tech.md`](tech.md)、[`frontend.md`](frontend.md) 为准。术语以 [`CONTEXT.md`](../CONTEXT.md) 为准。

**方式**四档：

- **直接依赖**：装进 `pyproject.toml` / `package.json`，用官方 API。
- **数据导入**：下载一次，写进图谱或 `data/`，运行时不调对方服务。
- **抄思路**：读机制，自己用 DeepSeek / Pydantic / Cypher 重写。
- **抄部分实现**：只搬分层、拦截或评测框架，不把整仓当依赖。

调研日期 2026-08-28；智联/51job/猎聘可用性复核 2026-08-30；公司官网招聘页 2026-09-03。star 和推送会变，装依赖前打开仓库页看一眼。

## 采集

| 用途 | 项目 | 方式 | 我们做什么 | 风险 |
|---|---|---|---|---|
| 冷启动 JD | 官方招聘门户 | 数据采集 | 字段映射后粗滤四领域，写入 `data/official-only/jd/`，再跑抽取 | 门户字段和排序会变化，需保留快照与检查点 |
| 条数补洞 | [天池智联人岗匹配](https://tianchi.aliyun.com/dataset/31623) | 数据导入 | 只补字段或条数缺口 | 偏匹配赛，正文不如现场 JD 厚 |
| 稳定公开源 | Greenhouse / Lever / Ashby JSON；[NCSS](https://www.ncss.cn/student/jobs/index.html) | 抄思路 | 自写 source，打公开列表/JSON | NCSS 无官方 API，页面改了要修 |
| 国内官网招聘页 | [Hiring-Radar](https://github.com/simonlin1212/Hiring-Radar)（飞书/Moka/北森 + 腾讯/字节等自建） | 抄思路 | 自写 source；先打已验证 JSON，加公司用配置行 | 门户域名和 `website-path` 会过期；Moka 有前端 AES 信封 |
| 国内大厂 URL 对照 | [FindJobs-Agent](https://github.com/he-yufeng/FindJobs-Agent) `job_crawler_v2.py` | 抄思路 | 只抄公司→端点，不引入 Agent | 阿里/美团/京东在仓内已走 Selenium |
| ATS 采集器参考 | [ats-scrapers](https://github.com/kalil0321/ats-scrapers)；[ats-job-apis](https://github.com/noble-ronin/ats-job-apis) | 抄思路 | 只抄端点形状，不 vendor、不 pip 装 | 覆盖偏海外 ATS；字节适配器打的是英文门户 |
| BOSS 增量 | [BossHunter](https://github.com/shengjidaguai-china/BossHunter) | 抄思路 | Playwright 已登录会话 + 拦 `joblist.json` | 账号会封；headless 易撞验证码 |
| 多站分层 | [RAYNLIU2005/-Multi-threadedCrawler](https://github.com/RAYNLIU2005/-Multi-threadedCrawler) | 抄部分实现 | `source / controller / sink` + fingerprint 幂等 | star 少，选择器会过期，当骨架不当时钟 |
| 猎聘/智联/51job 现网会话 | [AgentMesh-JobAgent](https://github.com/jiyangnan/AgentMesh-JobAgent) v0.5.40（2026-08-28） | 抄思路 | 受管 Chrome + 每站独立 source；失败即停 | 求职 Agent，云端收费；不要 vendor |
| 三站页面增强/本地快照 | [职位猎人 job-hunting](https://github.com/lastsunday/job-hunting) 扩展 5.0.0 | 排除（一期） | 不接进 worker | 插件不是采集库；README 禁商用 |
| 猎聘/智联拦截 | RAYNLIU 仓的数据包监听 | 抄思路 | `wait_for_response` 拦 JSON，不解析 DOM | 接口路径会变 |
| 事件总线 | Redis Stream | 直接依赖 | `XADD jobs:events`；SSE 仅管理可选 | 求职者页不订流，见前端篇 |
| SSE 出口 | [sse-starlette](https://github.com/sysid/sse-starlette) | 直接依赖 | `GET /events/stream` + `Last-Event-ID` | 只给管理/worker，不上 Kafka |
| 英文对照 | [JobSpy](https://github.com/speedyapply/jobspy) | 排除（一期） | 算法验证需要时再加 | LinkedIn 易限流 |

**排除。** 2019–2021 的 Scrapy 站群（JobWitcher、scrapy-51job、spider2、chenjiandongx/51job-spider）：选择器失效。纯 `requests` / cookie 重放（silie666/job-crawler）：过期。mcp-jobs：默认 headless 打首页，会撞墙。纯 `requests` 打 BOSS：账户级 `code: 36`。Kafka：单机过重。

细节：[research/jd-collection.md](research/jd-collection.md) · 三站可用性：[research/job-site-crawlers.md](research/job-site-crawlers.md) · 官网招聘页：[research/company-career-pages.md](research/company-career-pages.md)

## 图谱管线与存储

| 用途 | 项目 | 方式 | 我们做什么 | 风险 |
|---|---|---|---|---|
| 图库 | Neo4j Community 官方镜像 | 直接依赖 | 单容器 Bolt；边上 `valid_from/valid_to` + `EvolutionEvent` | 社区版单库、无角色，正好够 |
| 驱动 | 官方 `neo4j` Python | 直接依赖 | 参数化 Cypher | 不要再包一层 ORM |
| 双时间抽取 | [ATOM / iText2KG](https://github.com/AuvaLab/itext2kg) | 抄思路 | JD 切段后抽五元组；`t_obs` 与有效期分开 | pip 包学术节奏，不整仓引入 |
| 失效不删 / 溯源 | [Graphiti](https://github.com/getzep/graphiti) | 抄思路 | 旧边写 `valid_to`；证据当 episode | 不要拿它当主存储或主 API，episode 模型绑死查询 |
| 增量重建 | [LightRAG](https://github.com/HKUDS/LightRAG) | 抄思路 | 删源时只重建受影响岗位子图 | 定位是 RAG，不要当产品图 |
| 抽取模型 | DeepSeek `deepseek-v4-flash` | 直接依赖 | 非思考 + JSON + Pydantic，见技术篇 | 思考模式会拖慢批量 |
| 嵌入 | `BAAI/bge-m3` 本地 | 直接依赖 | `align_skill` 与聚类共用 | 官方 chat 无 embeddings 端点 |
| 抽取 UI 参考 | [neo4j-labs/llm-graph-builder](https://github.com/neo4j-labs/llm-graph-builder) | 抄思路 | 流程参考，不嵌他们的 Web | 通用文档抽取，schema 太松 |

**排除。** KuzuDB（上游归档）。Apache AGE（Cypher 缺口，无管线生态）。GraphRAG 整包（维护模式、批索引贵）。NetworkX 当主存储。Triplex（非商用许可 + 本地 GPU）。Graphiti 整包当后端。

备选（未选）：PG + AGE 仅在「只运维一个 PG」时；FalkorDB 仅在嫌 JVM 时，边上的有效期字段保持可平移。

细节：[research/kg-pipeline.md](research/kg-pipeline.md)

## 简历

| 用途 | 项目 | 方式 | 我们做什么 | 风险 |
|---|---|---|---|---|
| PDF 文本 | [pdfplumber](https://github.com/jsvine/pdfplumber) MIT | 直接依赖 | 读文本层 | 扫描件一期拒收 |
| Word | [python-docx](https://github.com/python-openxml/python-docx) MIT | 直接依赖 | `.docx` 段落；`.doc` 一期拒收 | |
| 结构化抽取 | DeepSeek JSON 分任务 | 自研 | 基本信息 / 技能点两路并行，过 `align_skill` | 双栏版式会掉点 |
| 版面与评测 | [SmartResume](https://github.com/alibaba/SmartResume) Apache-2.0 · [论文](https://arxiv.org/abs/2510.09722) | 抄思路；二期可抄部分实现 | 一期不引入版面模型；评测可搬匈牙利对齐 | 开源版 OCR 已换掉，能力打折 |
| 中文匹配二开 | [resume-matcher-agent-cn](https://github.com/liangdabiao/resume-matcher-agent-cn) | 抄思路 | 模块切分参考 | 英文上游，不是准确率基准 |
| NER 老路 | pyresparser、PaddleNLP 简历 NER | 排除 | 字段级 F1 过不了 90% | 停更或不含技能项级口径 |

金标自建 100 份中文简历（可加到 200），放 `data/eval-official-only/`。没有公开的中文技能项级基准。

细节：[research/resume-parsing.md](research/resume-parsing.md)

## 本体与产品交互

| 用途 | 项目 | 方式 | 我们做什么 | 风险 |
|---|---|---|---|---|
| schema 对照 | [ESCO v1.2.1](https://esco.ec.europa.eu/en/use-esco/download) | 对照（不挡冷启动） | 不导入、不手录；17 岗名见产品篇 | 无中文 |
| 技能点对照 | [O\*NET Software Skills](https://www.onetcenter.org/database.html)（原 Technology Skills）CC BY 4.0 | 对照（不挡冷启动） | 不导入、不手录；技能点从 JD 抽取聚类 | 职业层是美国 SOC |
| 中文岗位名 | 大典 2022 | 对照 | 编码可空；不挡步骤 1 | 无官方结构化技能层 |
| 数据模型模板 | [SkillsFuture SFw](https://jobsandskills.skillsfuture.gov.sg/frameworks/skills-frameworks) | 抄思路 | 岗位→技能点→熟练级；不用它的 6 级，用了解/熟练/精通 | 英文、体量小 |
| 本体管理工具 | [Tabiya taxonomy-model](https://github.com/tabiya-tech/taxonomy-model-application) MIT | 排除（一期） | ESCO 本地化可参考，不自建管理台 | 多一个前端 |
| 技能树交互 | [roadmap.sh](https://github.com/kamranahmedse/developer-roadmap) | 抄思路 | 工作台切片的疏密与点选，不嵌他们的路线图 | 进度打卡属账户体系，本期不做 |
| 测评闭环 | [My Next Move](https://www.mynextmove.org) | 抄思路 | 诊断档位 + 邻近岗，不做 RIASEC 问卷 | |
| 对话补技能 | [Tabiya Compass](https://github.com/tabiya-tech/compass) MIT | 排除（一期） | 简历稀疏时的后路，MVP 免登录不做聊天 | |
| Lightcast API | [Open Skills](https://lightcast.io/open-skills) | 排除 | 免费 API 已停 | 网页分类法可看，不可当底座 |

细节：[research/skill-taxonomy.md](research/skill-taxonomy.md)

## 可视化

| 用途 | 项目 | 方式 | 我们做什么 | 风险 |
|---|---|---|---|---|
| 图谱主体 | [AntV G6 v5](https://g6.antv.antgroup.com) MIT | 直接依赖 | 总览四领域图、工作台切片、诊断小图；Canvas；dagre LR | 大图 CPU，见 issue [#7402](https://github.com/antvis/G6/issues/7402)，关多余 behavior |
| React 壳 | 官方「在 React 中使用」 | 直接依赖 | 只要官方容器，不装 Graphin | Graphin 示例偏 v2 |
| Timebar / 蚂蚁线 / emitParticle | G6 插件与 react-force-graph | 排除（产品） | 地图已撤回采集流墙和演化回放 | 调研里仍有可行性，实现禁止装 Timebar |
| 周边统计 | ECharts | 排除（一期） | 热度条用 CSS，不上第二套图库 | graph 千级会卡，本来也不当主体 |
| sigma / cytoscape | | 排除 | | 无中文文档或动效不够 |

细节：[research/graph-viz.md](research/graph-viz.md)。页面约束：[frontend.md](frontend.md)。

## 运行时直接依赖（无调研专篇）

这些是栈本身，不来自五张调研，列在这里避免实现时另找轮子。

| 用途 | 项目 | 方式 | 备注 |
|---|---|---|---|
| HTTP | FastAPI | 直接依赖 | |
| 前端 | Next.js App Router + React | 直接依赖 | 样式拷 `prototypes/tokens.css`，不必为 tokens 再加 Tailwind |
| 浏览器采集 | Playwright | 可选 | 增量源；步骤 2 不挡。`headless=False` 或持久化 user data dir |
| 缓存 / 会话 / Stream | Redis 7 | 直接依赖 | |
| LLM SDK | OpenAI 兼容客户端，`base_url` 指 DeepSeek | 直接依赖 | 只允许 `app/llm/client.py` 调用 |
| 校验 | Pydantic | 直接依赖 | LLM JSON 与 Cypher 入参 |

## 自研清单

别人不替我们做、也不该做成「再包一层开源仓」的部分：

1. JD 切段、入池阈值、置信层、待审/直通、岗位状态机
2. `align_skill`、匹配分、档位、缺口集、换档条件、学习资源现查缓存
3. 五个产品路由与原型交互（切片画布含切片差分、诊断四拍、邻近岗并排、对照链接、口令、⌘K）
4. 技能聚类生成 `Skill` 与同义词；17 个规范岗位名对齐
5. `data/eval-official-only/` 金标与三项 set-based F1

新开源库想进仓库：先对这张表。能归到「排除」或「已有直接依赖」的，不装。
