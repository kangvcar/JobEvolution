# 开发计划与部署篇

给实现用的顺序、验收和一键部署。今天起算，赛题提交截止 **2026-09-05**。代码实现不在地图里，本文是开工后的路线。

先读：[`CONTEXT.md`](../CONTEXT.md) → [`product.md`](product.md) → [`tech.md`](tech.md) → [`frontend.md`](frontend.md) → [`verification.md`](verification.md) → [`research.md`](research.md)。页面以 [`prototypes/signature-ui.html`](prototypes/signature-ui.html) 为准。开源怎么抄见借鉴指南，不要直接按 `docs/research/` 五篇调研正文开工。

## 任务顺序

代码一步做完再开下一步。金标从步骤 2 叠着标，不占步骤顺序。每步有可检查的完成条件。AI 一次只领一步代码。

### 0. 骨架

compose 四个服务能起：`neo4j`、`redis`、`api` 健康检查、`web` 能打开五个空路由。`tokens.css` 拷进 `apps/web`。顶栏导航可点，内容可以是「未接数据」。

完成：`docker compose up --build` 后 `GET /meta` 200；`/` `/graph` `/diagnose` `/discover` `/admin` 都返回 200。

### 1. 图谱约束

Neo4j 约束与标签按技术篇。写入四个 `Domain`。17 个规范岗位名做成对齐靶子常量，名单见 [`product.md`](product.md)。不写 `Skill`、不写 `REQUIRES`、不写岗位 `status`。ESCO / O\*NET / 大典编码不挡本步，字段可空。

完成：Cypher 能查出四个领域；`GET /jobs` 可以空。工作台允许空切片。

### 2. 采集打底

`data/` 下所有本地 JD 表按标题粗滤四领域，字段映射后 fingerprint 幂等，写入 `data/jd/`，Redis Stream 有 `jd_ingested`。人工智能优先。不要限定某一家招聘站或某一个文件名。不要手写赛题 JD。天池只补洞。Playwright 增量不挡演示。

完成：去重后能列出 ≥100 条路径，四领域都有。金标 JSONL 从本步起手。

### 3. 抽取与闸

DeepSeek JSON + Pydantic。技能字符串先聚类成 `Skill`，再 `align_skill`。入池 30%、置信三层、待审队列、直通开关。岗位名对上 17 个靶子或进发现簇。既有岗更新与新岗发现同一套闸。状态由独立源计票。

完成：大模型应用工程师能查出 `REQUIRES` 与 `EvolutionEvent`；Agent 工程师在有 ≥3 独立源时为萌芽。低置信不可 auto_passed。管理页能批/驳。「LLM 业务工程师」由簇判别写 `ALIAS_OF`。不要手补节点或状态。

### 4. 诊断

简历 pdfplumber / python-docx → 会话 → `POST /diagnose`。四拍只是等待动画，字幕用人话。报告四组按产品篇：学习路径按换档条件排序，邻近岗并排，done 可复制对照链接。档位阈值与原型一致。诊断默认岗：大模型应用工程师。

完成：放一份演示 PDF，档位和缺口集与金标对得上方向（此时金标可以还是草稿）；换到 Agent 工程师仍停在 done。

### 5. 发现与总览

候选 / 萌芽 / 成型看板。总览四领域图点岗进工作台。第一屏只有故事和萌芽 / 谱内；管线、热度、流水在发现页和总览 `<details>`。计数走库聚合，不订 SSE 粒子。

完成：发现页三列能看见候选 / 六萌芽 / 成型切片；候选卡不能进工作台、不能诊断；总览第一屏看不到待审 / 拦下 / 簇。

### 6. 评测与提交物

按 [`verification.md`](verification.md) 建 `data/eval/`，冻 `freeze.json`，三项 F1 脚本 + `pytest --cov-fail-under=60`。dump `deliver/agent` 与 `deliver/llm-app`。

完成：三项 ≥0.90（未 mock 的本地跑，写入 `summary.md`）、覆盖率 ≥60%、两岗 io.md 有真字段。ATS / NCSS 有则补，没有不挡提交。CI 的 mock F1 不是提交分。

不要并行拆「先做炫的图」。G6 只服务步骤 1 的切片（含切片差分）和总览图。

## docker compose

仓库根目录 `docker-compose.yml`，服务四个：

| 服务 | 镜像 / 构建 | 端口 | 卷 |
|---|---|---|---|
| neo4j | `neo4j:5-community` | 7687 Bolt，7474 浏览器可选 | `neo4j_data` |
| redis | `redis:7-alpine` | 6379 | 可不持久化 |
| api | `apps/api` Dockerfile | 8000 | 挂 `data/` |
| web | `apps/web` Dockerfile | 3000 | 无 |

`NEO4J_AUTH` 用环境文件，社区版单库。api 等 neo4j healthy 再起。web 的 `NEXT_PUBLIC_API_URL` 指到 `http://localhost:8000`（浏览器访问时）或 compose 内网名（SSR 时）。

内存：Neo4j 堆+页缓存合计 1–2GB 够。整机建议 8GB。bge-m3 第一次拉取放进 api 镜像或启动时下载到卷，避免每次冷启动。

一键：

```
cp .env.example .env   # 填 DEEPSEEK_API_KEY、ADMIN_PASSWORD
docker compose up --build
```

不要再加 Postgres、Kafka、独立 Graphiti 容器。

## 环境变量

| 名 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | 只进 api |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-v4-flash` |
| `NEO4J_URI` | 是 | `bolt://neo4j:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | 是 | 与 compose `NEO4J_AUTH` 一致 |
| `REDIS_URL` | 是 | `redis://redis:6379/0` |
| `ADMIN_PASSWORD` | 是 | 管理口令，常量时间比较 |
| `ALIGN_THRESHOLD` | 否 | 运行时默认 0.85；**评测忽略此项**，只读 `data/eval/freeze.json` |
| `NEXT_PUBLIC_API_URL` | 是（web） | 浏览器打 api |

密钥不进 git。`.env` 在 `.gitignore`。演示机用单独口令，不要用 `neo4j/neo4j` 默认密码对外。

Playwright 用户目录若做增量采集，路径放 `PLAYWRIGHT_USER_DATA`，不进镜像。

## 演示准备

截止日前要能在一台机器上走完两条主路径，不注册。

1. compose 全绿；口令能进待审。
2. 总览第一屏能点到故事：打开工作台、对照这份岗。工作台切片能开证据，大模型应用岗能看见本周期切片差分（新增或已写 `valid_to`）。
3. 诊断默认大模型应用工程师，上传演示简历出四组报告，档位不是 0–100 大数字；学习路径按换档条件排；邻近岗能并排切到 Agent 工程师。
4. 发现页三列能讲漏斗：候选未入谱、Agent 工程师萌芽（≥3 独立源，公司名）、大模型应用已拆开。候选卡不能对照简历。
5. 待审里有一条中置信升必备和一条低置信：确认可点，文案写不可直通。这两条对得上本次管线，不要手写进队列。
6. `data/eval/deliver/` 两岗目录齐，评委可打开 io.md，字段对得上本次管线。
7. 打印 `data/eval/out/summary.md`：三项 F1、覆盖率。
8. 复制对照链接，同一会话未过期能再打开报告。

演示简历放 `data/eval/demo-cv.pdf`（可脱敏）。不要依赖现场再爬 BOSS。缺独立源的岗停在候选，不要手写萌芽/成型。

## 文档对照

实现以这六篇加术语表为准。下面几条曾经改过口，不要按工单早期正文或调研原文反悔：

| 曾出现 | 以谁为准 |
|---|---|
| 暗色大屏、采集流墙、Timebar 回放 | 产品篇 / 前端篇：不做 |
| 导航「图谱·诊断·新兴」 | 产品篇：总览·图谱·诊断·发现 |
| 学习路径前 3 步 / 按缺口出现顺序取 5 | 术语表 / 技术篇 / 前端篇 / 原型：按换档条件排序，默认最多 5 |
| 图谱第三筛选 = 熟练级 | 前端篇 / 原型：适用级别 `levels` |
| 低置信确认按钮禁用 | 前端篇 / 原型：可批，不可直通 |
| 发现页藏起候选 | 产品篇 / 原型：三列漏斗；候选只开卷宗，别名不占列 |
| 边指向 REQUIRES | 技术篇：证据 id 写在属性上 |
| Graphiti / Kafka / Postgres 主存储 | 技术篇：不上 |
| 匹配分展示成大数字 | 产品篇：只展示档位 |
| 签名交互 = 蚂蚁线 + 时间轴 | 前端篇：切片画布（含切片差分）+ 诊断四拍（人话） |
| 总览第一屏带管线 / 待审 / 拦下 | 产品篇 / 前端篇 / 原型：管线在发现页和总览折页 |
| 诊断四拍念 0.5 / 0.3 | 前端篇 / 原型：人话；数字只在解释组 |
| 萌芽 / 演化只写种子 | 术语表 / 技术篇：一律由管线从证据计票，不手写 status |
| 登录后才能保存对照 | 产品篇：本期对照链接，不上登录 |
| 高默认可直通 | 术语表 / 技术篇：直通关着，高也进待审 |
| 手录 17 岗 + 60 技能点 + `bootstrap.py` | 技术篇：17 岗名是对齐靶子；技能点 / 边 / 状态从 `data/` 本地 JD 管线出 |
| 天池冷启动 / 只认智联年度 CSV | 技术篇：`data/` 下所有本地 JD 表，不限站、不限文件名 |
| O\*NET / 大典数据导入 | 技术篇：对照，字段可空，不挡、不手录 |
| Playwright 必装 | 借鉴指南：可选，不挡演示 |
| 候选簇含别名 | 产品篇 / 原型：不计别名，两处都是 3 |
| Graphin 当壳 | 前端篇：官方 React 容器 |

`docs/research/*.md` 是调研档案，结论冲突时听六篇定案。

## 地图收口

目的地是这六份文档，不含实现代码。本篇写完，规划侧没有未决工单。实现按本文第 0–6 步开工即可。
