# 开发计划与部署篇

给实现用的顺序、验收和一键部署。今天起算，赛题提交截止 **2026-09-05**。代码实现不在地图里，本文是开工后的路线。

先读：[`CONTEXT.md`](../CONTEXT.md) → [`product.md`](product.md) → [`tech.md`](tech.md) → [`frontend.md`](frontend.md) → [`verification.md`](verification.md) → [`research.md`](research.md)。页面以 [`prototypes/signature-ui.html`](prototypes/signature-ui.html) 为准。开源怎么抄见借鉴指南，不要直接按 `docs/research/` 里早期「暗色大屏 / Timebar」段落开工。

## 任务顺序

一步做完再开下一步。每步有可检查的完成条件。AI 一次只领一步。

### 0. 骨架

compose 四个服务能起：`neo4j`、`redis`、`api` 健康检查、`web` 能打开五个空路由。`tokens.css` 拷进 `apps/web`。顶栏导航可点，内容可以是「未接数据」。

完成：`docker compose up --build` 后 `GET /meta` 200；`/` `/graph` `/diagnose` `/discover` `/admin` 都返回 200。

### 1. 图谱冷启动

Neo4j 约束与标签按技术篇。导入 ESCO 骨架裁剪 + O\*NET 技能点种子 + 大典编码。写入 17 岗、约 60 技能点、6 萌芽状态，见 [决策:首批岗位覆盖清单](https://github.com/kangvcar/JobEvolution/issues/18)。

完成：Cypher 能查出 Agent 工程师 `status=emerging`、大模型应用工程师 `status=formed`；工作台能画当前岗切片。

### 2. 采集打底

天池 JD 导入 `data/jd/`，fingerprint 幂等，Redis Stream 有 `jd_ingested`。Playwright 增量可后做，本步不挡演示。

完成：去重后能列出 ≥100 条路径（不足则先用天池凑满评测集，现场源在第 6 步补）。

### 3. 抽取与闸

DeepSeek JSON + Pydantic。`align_skill`、入池 30%、置信三层、待审队列、直通开关。既有岗更新与新岗发现同一套闸。

完成：用大模型应用工程师的若干 JD 跑通，能产出 `REQUIRES` 与 `EvolutionEvent`；低置信不可 auto_passed。管理页能批/驳。

### 4. 诊断

简历 pdfplumber / python-docx → 会话 → `POST /diagnose`。四拍只是等待动画。报告四组按产品篇。档位阈值与原型一致。诊断默认岗：大模型应用工程师。

完成：放一份演示 PDF，档位和缺口集与金标对得上方向（此时金标可以还是草稿）。

### 5. 发现与总览

候选 / 萌芽 / 成型看板。总览四领域图点岗进工作台。计数走库聚合，不订 SSE 粒子。

完成：六萌芽出现在发现页；候选只在待审。

### 6. 评测与提交物

按 [`verification.md`](verification.md) 建 `data/eval/`，冻 `freeze.json`，三项 F1 脚本 + `pytest --cov-fail-under=60`。dump `deliver/agent` 与 `deliver/llm-app`。

完成：三项 ≥0.90、覆盖率 ≥60%、两岗 io.md 有真字段。现场 JD 若第 2 步不够，这里用 ATS/NCSS 补到「不少于三分之一」。

不要并行拆「先做炫的图」。G6 只服务步骤 1 的切片和总览图。

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
2. 总览能点到 17 岗；工作台切片能开证据。
3. 诊断默认大模型应用工程师，上传演示简历出四组报告，档位不是 0–100 大数字。
4. 发现页能讲 Agent 工程师萌芽：≥3 独立源、与大模型应用已拆开。
5. 待审里有「评测集构建」升必备（中置信）和一条低置信不可直通。
6. `data/eval/deliver/` 两岗目录齐，评委可打开 io.md。
7. 打印 `data/eval/out/summary.md`：三项 F1、覆盖率。

演示简历放 `data/eval/demo-cv.pdf`（可脱敏）。不要依赖现场再爬 BOSS。

## 文档对照

实现以这六篇加术语表为准。下面几条曾经改过口，不要按工单早期正文或调研原文反悔：

| 曾出现 | 以谁为准 |
|---|---|
| 暗色大屏、采集流墙、Timebar 回放 | 产品篇 / 前端篇：不做 |
| 导航「图谱·诊断·新兴」 | 产品篇：总览·图谱·诊断·发现 |
| 学习路径前 3 步 | 技术篇 / 前端篇：默认 5 |
| 图谱第三筛选 = 熟练级 | 前端篇：适用级别 `levels` |
| Graphiti / Kafka / Postgres 主存储 | 技术篇：不上 |
| 匹配分展示成大数字 | 产品篇：只展示档位 |
| 签名交互 = 蚂蚁线 + 时间轴 | 前端篇：切片画布 + 诊断四拍 |

`docs/research/*.md` 是调研档案，结论冲突时听六篇定案。

## 地图收口

目的地是这六份文档，不含实现代码。本篇写完，规划侧没有未决工单。实现按本文第 0–6 步开工即可。
