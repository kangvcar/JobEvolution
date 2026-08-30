# 调研:招聘数据采集开源方案与公开 JD 数据集

> **档案。** 定案以 `docs/product.md`、`docs/tech.md`、`docs/frontend.md` 为准。冷启动已改为仓库 `data/` 下全部本地 JD，不限智联、不限文件名；不再手录图谱、也不以天池为人手。求职者页不做实时采集动效；SSE 只给管理可选。
> 关联工单:GitHub issue #2(Part of #1) · 赛题 XH-202621「多源异构数据驱动岗位和能力图谱构建与动态演化分析」
> 技术栈约束:Python + FastAPI 优先;需要多源采集中文招聘 JD。
> 合规:用户明示忽略 robots 等限制,本文只做技术可行性判断,不做法律/合规背书。
> 核查时间:2026-08-28。智联 / 51job / 猎聘仓库可用性复核见 `docs/research/job-site-crawlers.md`(2026-08-30)。仓库 star / 最近推送时间会漂移,依赖前请以仓库页面为准。

## 0. 一句话结论

主流招聘站(BOSS/拉勾/猎聘/智联)没有"开箱即用还稳定"的 requests 型爬虫——它们全部转向**真实登录浏览器会话 + 接口拦截**才能活下来;真正低成本、稳定、可增量的公开源是**公司官网 careers 页背后的 ATS(Greenhouse/Lever/Ashby)**和**高校/政府就业平台(NCSS)**;冷启动直接用**天池「智联招聘人岗智能匹配」数据集**把图谱和前端跑通。事件流用 **Redis Stream + FastAPI(sse-starlette)SSE** 这一套轻量组合即可,不必上 Kafka。

---

## 1. 主流招聘网站爬虫开源项目

### 1.1 核心事实:反爬现状(一手来源)

- BOSS 直聘对**纯 HTTP 请求(`requests`)会直接返回 `code: 36「您的账户存在异常行为」`并做账户级封禁**——因为缺真实浏览器的 TLS 指纹、`__zp_stoken__`(JS 动态令牌)、Cookie 管理和 JS 环境。见上游 `mcp-bosszp` 的重构 PR 和下游 issue 的根因分析:
  - <https://github.com/Panniantong/mcp-bosszp/pull/1>(把 API 调用从 `requests.Session` 改为在 Playwright 浏览器内用 `fetch()` 发起,附反自动化特征处理:`navigator.webdriver` 覆盖、中文 locale/时区、Geetest 检测)
  - <https://github.com/Panniantong/Agent-Reach/issues/56>(结论:登录能成功,但后续 API 调用"太像机器人"被风控拦;维护者称 BOSS 渠道"半废",建议本地家庭 IP 运行、住宅代理、降低频率)
- 可行范式是 **Playwright 接口拦截**:`page.wait_for_response(lambda r: "joblist.json" in r.url)` 直接拿结构化 JSON,比解析 DOM 快 3–5 倍且更稳(接口比 DOM 稳定)。BOSS 的关键接口:`/wapi/zpgeek/search/joblist.json`(搜索列表)、`/wapi/zpgeek/job/*.json`(职位详情)、`/wapi/zpgeek/company/*.json`(公司)。

### 1.2 候选清单

| 项目 | 覆盖站点 | 技术路线 | star / 最近推送 | 维护状态 | 取舍 |
| --- | --- | --- | --- | --- | --- |
| [shengjidaguai-china/BossHunter](https://github.com/shengjidaguai-china/BossHunter) | BOSS 直聘 | Chrome 本地自动化 + AI 评分 + 人工确认投递 | 527★ / 2026-08-28 | **活跃(当天仍在推送)** | 最值得借鉴的 BOSS 采集范式:真实浏览器、离线城市目录、可恢复任务、幂等去重。是个人求职 Agent 而非纯采集器,需裁剪投递/简历模块 |
| [HeyClioo/boss-zhipin-jd-scraper](https://github.com/HeyClioo/boss-zhipin-jd-scraper) | BOSS 直聘 | 驱动"你自己已登录的真实浏览器"抓完整 JD,去水印、按 job ID 去重、导出 Markdown | 4★ / 2026-07-14 | 新、小而专 | 定位是 Claude/Codex 技能而非库;明确写"headless 会撞验证码墙,必须真实浏览器"。适合抄它的"绕反爬"思路,不适合直接当后端组件 |
| [RAYNLIU2005/-Multi-threadedCrawler](https://github.com/RAYNLIU2005/-Multi-threadedCrawler) | BOSS / 51job / 智联 / 猎聘 | 多进程/线程 + 三层解耦(source→controller→sink),CSV/MySQL 落地,**可一键切 Kafka 总线** | 2★ / 2025-10-26 | 较新、结构清晰 | **架构最贴合本项目**:`source/controller/sink/bus` 分层、`fingerprint` 幂等、猎聘用数据包监听(`searchfront4c.pc-search-job`)+ 拟人滚动/鼠标/延迟。star 少,当参考架构而非依赖 |
| [hypier/scrapy-51job](https://github.com/hypier/scrapy-51job) | 51job / 猎聘 / 拉勾 / 智联 / BOSS | Scrapy + Redis(地址缓存)+ ES,可接入 crawlab 平台 | 18★ / 2020-09 | **过时(2020)** | README 自己标注"BOSS 易被反爬"。Scrapy+Redis+crawlab 的增量与调度思路可借鉴,选择器基本已失效 |
| [igaozp/JobWitcher](https://github.com/igaozp/JobWitcher) | 智联 / 拉勾 / 51job / BOSS / 猎聘 | Scrapy + Redis 增量 + MySQL | 7★ / 2019-07 | **过时(2019)** | 五站点合集的目录组织可参考,解析规则已失效 |
| [yuyong513/spider2](https://github.com/yuyong513/spider2) | 30+ 招聘站(看准/BOSS/51job/智联/拉勾/猎聘…) | 线程池+协程+异步,requests+伪造 UA+IP 代理池,MongoDB/Redis,APScheduler 定时 | 0★ / 2021-12 | **过时(2021)** | 站点覆盖面最广、定时+代理池思路可参考,但 requests 路线对今天的 BOSS 已失效 |

### 1.3 取舍结论

- **不要指望现成 requests 型爬虫**:5 个多站合集里 3 个已 2019–2021 停更,选择器和反爬对抗全部过期。
- **BOSS 直聘**:唯一可行路线是 BossHunter 代表的"真实登录浏览器 + 接口拦截"。用 Playwright(`headless=False` 或持久化用户目录)+ `wait_for_response` 抓 `joblist.json`,配拟人行为与低频。**主账号有被封风险**,建议小号 + 本地/住宅 IP。
- **猎聘/智联/51job**:同样走真实浏览器会话。2026-08-30 复核:还在跟现网改版的是 AgentMesh-JobAgent(三站独立模块,智联 8 月 22–23 日仍在修)和职位猎人插件;RAYNLIU 只当分层骨架。清单和可用性判断见 `docs/research/job-site-crawlers.md`。

---

## 2. 公开 JD 数据集(中文优先)

| 数据集 | 语言 | 规模 / 字段 | 获取 | 取舍 |
| --- | --- | --- | --- | --- |
| [天池「智联招聘人岗智能匹配」](https://tianchi.aliyun.com/dataset/31623) / [初赛数据集](https://tianchi.aliyun.com/dataset/44080) | 中文 | 人岗匹配比赛数据(职位 + 求职行为) | 天池账号免费下载;参考解题仓库 [juzstu/TianChi_ZhiLianZhaoPin](https://github.com/juzstu/TianChi_ZhiLianZhaoPin)(71★) | **冷启动首选**:免爬取、可离线,足够把"岗位—能力图谱 + 前端动效"跑通。偏"匹配"任务,JD 正文字段不如真实采集丰富 |
| 智联招聘 1300 万条库(2016–2025.7) | 中文 | 1332 万条;含职位描述、学历、经验、薪资、发布/结束时间等 20 字段 | [经管之家](https://bbs.pinggu.org/thread-16384682-1-1.html) / [马克数据网](https://www.macrodatas.cn/article/1147473628) | 字段最贴合"岗位演化分析"(带时间范围,可做动态演化)。**付费商业数据**,非开源;适合正式分析阶段按需购买 |
| [Kaggle: Data Science Job Postings with Salaries (2025)](https://www.kaggle.com/) | 英文 | DS 岗位 + 薪资,经 LLM 清洗 | Kaggle 免费(仅限教育/研究,非商用) | 英文补充,做技能抽取 pipeline 的验证集 |
| [Kaggle: LinkedIn Data Analyst Jobs (USA/Canada/Africa)](https://www.kaggle.com/datasets/cedricaubin/linkedin-data-analyst-jobs-listings) | 英文 | 8,490 条,含 `title/company/location/description` | Kaggle 免费 | 字段规整、量适中,适合英文 skill 抽取 baseline |

取舍:**中文优先用天池数据集冷启动**;需要"时间维度演化"再评估 1300 万条商业库;英文数据集仅作抽取算法的补充验证。

---

## 3. 政府就业平台 / 高校就业网 / 公司官网 careers 采集可行性

| 渠道 | 可行性 | 依据 | 取舍 |
| --- | --- | --- | --- |
| **公司官网 careers 页(背后是 ATS)** | **最高** | Greenhouse/Lever/Ashby/Workday 有稳定的公开 JSON 端点,几乎无风控。开源采集器 [ats-scrapers/jobhive](https://scrapfly.io/blog/posts/best-open-source-job-scrapers)(50+ ATS,pandas 输出)、[Levergreen](https://github.com/)(Greenhouse/Lever,Scrapy+dbt+Postgres) | **稳定性/合规风险最低,强烈推荐作为主力公开源**。缺点:覆盖的是"用海外 ATS 的公司",国内中小企业覆盖有限 |
| **NCSS 国家大学生就业服务平台** ([www.ncss.cn](https://www.ncss.cn/student/jobs/index.html)) | 高 | 官方公开职位列表页(职位/专场/实习/重点领域),无需登录即可浏览;已有第三方 [Apify NCSS Jobs Scraper](https://apify.com/getascraper/ncss-jobs-scraper/api/python) 证明可结构化抽取(jobId/title/salary/education/majors/companyType/openings 等字段) | **无官方开放 API**,但公开页面/内部 JSON 接口可采;字段规范、权威、中文,适合做高校/应届岗位子集。政府站点采集需注意频率与稳定性 |
| **高校就业信息网 / 省级就业网** | 中 | 各校/各省站点异构,多为公开列表;有商业案例做"高校招聘数据智能采集+可视化"(requests+jieba+pyecharts,按职业大类分页采集、增量更新) | 覆盖长尾但**每个站点要单独写解析器**,维护成本高;适合定向补充特定学校/地区 |
| 政府公共招聘网(如中国公共招聘网及地方人社) | 中 | 公开岗位列表,结构相对稳定 | 数据偏基层/蓝领,与"能力图谱"技能岗位重合度视赛题定位而定 |

取舍:把**ATS + NCSS 作为"稳定公开主力源"**(低风控、字段规范),主流商业招聘站作为"高价值但高风险的增量源",高校/政府长尾站按需定向接入。

---

## 4. 增量采集 + 事件流(供前端"实时采集动效"消费)

### 4.1 方案对比

| 方案 | 定位 | 是否持久化/可回放 | 复杂度 | 适配本项目 |
| --- | --- | --- | --- | --- |
| **Redis Stream** | 采集事件总线(`XADD`/消费组) | ✅ 持久化 + 可按 ID 回放 | 低(已常用 Redis) | **推荐做事件骨干**:可配合 SSE 的 `Last-Event-ID` 做断线续传/补发 |
| Redis Pub/Sub | 跨进程广播 | ❌ fire-and-forget,零订阅即丢 | 极低 | 仅适合"纯实时、丢了无所谓"的动效帧;要可靠交付用 Stream |
| **SSE(sse-starlette)** | 服务端 → 前端单向推送 | — | 低 | **推荐做前端出口**:HTTP 单向、自动重连、穿透代理,天生适合"采集进度/动效"这种只下行的场景 |
| WebSocket | 双向 | — | 中 | 采集动效是单向下行,双向属过度设计 |
| Kafka | 重型分布式日志 | ✅ | 高(需集群/运维) | **不推荐**:比赛/单机场景过重,Redis Stream 已覆盖需求 |

一手依据:
- `sse-starlette` 提供 `EventSourceResponse`,自动设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`,内置 ping 心跳(`: ping\n\n`)防代理 60s 空闲超时,并自动处理断连——这两点是手写 `StreamingResponse` 最容易出错的地方。仓库 [sysid/sse-starlette](https://github.com/sysid/sse-starlette)(849★,2026-08-14 推送,活跃)。参考实现指南 <https://www.server-sent-events.com/backend-stream-generation-connection-management/python-fastapi-sse-implementation-guide/>。
- 多进程/多实例下,需要 Redis 做 backplane 把事件 fan-out 到所有连接;**Pub/Sub 是 fire-and-forget,重连有间隙会丢消息,需要可靠交付/回放就用 Stream**(配合 SSE `Last-Event-ID`)。见 <https://www.server-sent-events.com/backend-stream-generation-connection-management/redis-pubsub-fanout-for-sse/broadcasting-sse-events-with-redis-pubsub/>。

### 4.2 推荐架构(数据流)

```
采集 Worker(Playwright/ATS 抓取)
   │  每抓到/入库一条 JD、每完成一页、每命中一个技能
   ▼
Redis Stream  jobs:events   (XADD, 事件带 id/type/payload)
   │
   ▼
FastAPI 端点  GET /events/stream  (sse-starlette EventSourceResponse)
   │  async 生成器 XREAD 消费,支持 Last-Event-ID 回放
   ▼
前端 EventSource  →  "实时采集动效"(计数跳动、节点在图谱上点亮)
```

- **增量与去重**:沿用参考项目的做法——以 `fingerprint`(公司名+职位名+来源,或站点 job ID)做唯一键幂等写库(见 `RAYNLIU2005/-Multi-threadedCrawler` 的 `DualWriter`);Redis 存已抓 ID 集合做增量判定(见 JobWitcher/scrapy-redis 思路)。
- **事件语义**:采集 Worker 每产生一条新 JD / 每解析出一个技能节点,就 `XADD` 一条事件;前端据此播放动效。断线时用 `Last-Event-ID` 从 Stream 回放,避免动效丢帧。

---

## 5. 推荐组合(落地建议)

1. **冷启动(第 1 步,不碰爬虫)**:天池「智联招聘人岗智能匹配」数据集 → 先把"JD → 技能抽取 → 岗位能力图谱 → 前端动效"全链路跑通。
2. **稳定公开主力源**:公司 careers 页 ATS(Greenhouse/Lever/Ashby,参考 jobhive)+ NCSS 国家大学生就业服务平台公开职位。低风控、字段规范、可持续增量。
3. **高价值增量源(高风险)**:BOSS/猎聘/智联,统一走 **Playwright 真实会话 + 接口拦截**(架构抄 `RAYNLIU2005/-Multi-threadedCrawler` 的 `source/controller/sink`,BOSS 反爬细节抄 `shengjidaguai-china/BossHunter`)。用小号 + 本地/住宅 IP + 低频。
4. **英文补充**:`JobSpy`([speedyapply/JobSpy](https://github.com/speedyapply/jobspy),4176★,2026-02,一次调用聚合 LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter → pandas)做算法验证与国际对照。LinkedIn 约第 10 页触发限流,需代理。
5. **事件流**:Redis Stream(事件骨干,幂等+回放)+ FastAPI `sse-starlette`(前端 SSE 出口)。**不上 Kafka**。

### 取舍一句话总结

- 选 ATS/NCSS 而非死磕 BOSS:**用最小对抗成本换稳定数据**;主流站作为高价值但需要真实浏览器会话的增量层。
- 选 Redis Stream+SSE 而非 Kafka/WebSocket:**在已有 Redis 基础上零新增重型依赖**,单向下行 + 可回放,正好匹配"实时采集动效"。
- 选真实浏览器接口拦截而非 requests+DOM:**接口比 DOM 稳、比 HTTP 请求更能过风控**,是当前唯一还能用的主流站路线。

---

## 附:关键链接汇总

- BOSS 反爬根因与浏览器化改造:<https://github.com/Panniantong/mcp-bosszp/pull/1> · <https://github.com/Panniantong/Agent-Reach/issues/56>
- BOSS 采集范式:<https://github.com/shengjidaguai-china/BossHunter> · <https://github.com/HeyClioo/boss-zhipin-jd-scraper>
- 多站分层框架(可切 Kafka):<https://github.com/RAYNLIU2005/-Multi-threadedCrawler>
- 天池数据集:<https://tianchi.aliyun.com/dataset/31623> · <https://tianchi.aliyun.com/dataset/44080> · <https://github.com/juzstu/TianChi_ZhiLianZhaoPin>
- ATS/开源招聘采集器横评:<https://scrapfly.io/blog/posts/best-open-source-job-scrapers>
- NCSS 平台:<https://www.ncss.cn/student/jobs/index.html> · <https://apify.com/getascraper/ncss-jobs-scraper/api/python>
- 英文聚合库:<https://github.com/speedyapply/jobspy>
- SSE:<https://github.com/sysid/sse-starlette> · <https://www.server-sent-events.com/backend-stream-generation-connection-management/python-fastapi-sse-implementation-guide/>
- Redis 广播 SSE:<https://www.server-sent-events.com/backend-stream-generation-connection-management/redis-pubsub-fanout-for-sse/broadcasting-sse-events-with-redis-pubsub/>
