# 调研:智联 / 51job / 猎聘开源爬虫(2026-08-30)

> **档案。** 定案以 `docs/product.md`、`docs/tech.md` 为准。冷启动与 ATS/NCSS 仍见 `docs/research/jd-collection.md`。
> 合规:只做技术可行性判断,不做法律背书。本文不写绕过风控的步骤或可用 payload。
> 核查时间:2026-08-30。star / 推送会变,装之前打开仓库页。
> 可用性口径:看仓库最近提交、站点选择器是否还在修、作者是否承认要登录浏览器。**没有在本机对三站实跑**,下表是仓库证据,不是「我跑通了」。

## 0. 一句话结论

三个站都没有面向采集的公开 JD API。2026 年还能跟页面改版的开源实现,只剩两条线:

1. **用户自己的已登录 Chrome 会话**(Playwright / Selenium / 浏览器插件),再拦页面里的 JSON 或读当前 DOM。
2. **过期 cookie 重放 / Scrapy 选选择器**。2018–2024 的合集基本废了。

最值得看的是 [jiyangnan/AgentMesh-JobAgent](https://github.com/jiyangnan/AgentMesh-JobAgent)(三站各有独立模块,智联 2026-08-22～23 还在修城市跳转,v0.5.40 发于 2026-08-28)和 [lastsunday/job-hunting](https://github.com/lastsunday/job-hunting)(423★ 浏览器插件,三站都列在支持表,扩展 5.0.0 发于 2026-06-30)。两者都是求职工具,不是可 `pip install` 的采集库。不要当依赖。

本项目用仓库 `data/` 本地 JD 冷启动。三站只当高风险增量,自己写 `source`,分层抄 [RAYNLIU2005/-Multi-threadedCrawler](https://github.com/RAYNLIU2005/-Multi-threadedCrawler)。

---

## 1. 智联招聘

搜索页现在是 `https://sou.zhaopin.com/`。老 Scrapy 还在打 `sou.zhaopin.com/jobs/searchresult.ashx`,那条路 2019 左右就废了。

| 项目 | 路线 | ★ / 最近推送 | 可用性 |
| --- | --- | --- | --- |
| [jiyangnan/AgentMesh-JobAgent](https://github.com/jiyangnan/AgentMesh-JobAgent) | 本机受管 Chrome + CDP;`jobagent zhilian login/discover`;独立 `platforms/zhilian/`(session/collect/parser/selectors) | 35★ / **2026-08-28**(v0.5.40) | **三站里证据最硬。** 2026-08-22～23 连续修登录跳转、旧城市码、搜索页无账号区、卡片解析失败。有 headed Chrome gate(`zhilian-headed-public-gate.yml`)。云端决策收费,采集本身走本地会话。Apache-2.0 客户端。 |
| [lastsunday/job-hunting](https://github.com/lastsunday/job-hunting) | Chrome/Edge 插件,增强搜索页,本地职位快照 | 423★ / 仓 2026-08-28;扩展 **5.0.0 @ 2026-06-30** | **能用,但不是爬虫。** README 写明对象是 `sou.zhaopin.com` 搜索页。适合人工浏览时落本地库,不适合当 FastAPI worker。 |
| [LoboNoRoot/zhilianZhaopin-scraper-spider](https://github.com/LoboNoRoot/zhilianZhaopin-scraper-spider) | Selenium,正则抽页面内嵌 JSON(`positionName`/`jobDesc`/`skillLabel` 等 20+ 字段),断点续爬 | 2★ / **2026-08-04** | 2026 年还在改 README 的少数专用智联爬虫。论文/课程作业气质,绑 ChromeDriver。未看到对外 breakage 报告,也没 CI。当参考字段映射,不当依赖。 |
| [silie666/job-crawler](https://github.com/silie666/job-crawler) | Go,HTTP + 配置里填智联 cookie(`at`/`rt`/`acw_tc`/`x-zp-client-id`) | 16★ / 2024-04-24 | 作者自己写「要登录才能看被隐藏岗位」。cookie 重放对智联过期很快,**按 2026 年标准当失效**。 |
| [wqh0109663/JobSpiders](https://github.com/wqh0109663/JobSpiders) | Scrapy「扒接口」 | 201★ / 2023-08-14 | star 最多的教学仓之一。接口签名和页面都换过代,**不可用**。 |
| [Chauncey2/zhaopin_spider](https://github.com/Chauncey2/zhaopin_spider) / [blackyau/zhaopin](https://github.com/blackyau/zhaopin) / [kevinleeex/ZLAnalyzer](https://github.com/kevinleeex/ZLAnalyzer) | Scrapy / 老搜索 URL | 7–17★ / 2017–2019 | 坟场。搜索 URL 和加密方式都对不上现在的站。 |

取舍:要跟现网智联,只抄 AgentMesh 的「受管 Chrome + 失败即停 + 城市证据交叉验证」,不要抄它的投递/云端计费。作业级 Selenium 最多借字段名。

---

## 2. 前程无忧(51job)

现网搜索页是 `https://we.51job.com/pc/search`。大量老仓还在打 `search.51job.com` 或已下线的 APP 接口。

| 项目 | 路线 | ★ / 最近推送 | 可用性 |
| --- | --- | --- | --- |
| AgentMesh-JobAgent | `jobagent 51job login/discover`;`platforms/job51/`;投递以 `we.51job.com` 为准,不信旧历史域 | 同上 / 2026-08-28 | **还在维护。** 有 `job51-headed-delivery-recovery-gate.yml`。README 写清:点了投递但证据不够就记 `delivery_indeterminate`,不重点。采集模块和智联同级隔离。 |
| lastsunday/job-hunting | 插件增强 `we.51job.com/pc/search` | 同上 | 支持表和截图都以 51job 搜索页为主。能用,仍是插件不是 worker。 |
| [jolie-z/Auto-JobHunter](https://github.com/jolie-z/Auto-JobHunter) | Playwright + `51job_scraper/` + cookie harvester;SQLite | 73★ / 2026-04-27 | 2026 年写过,目录还在。绑 **macOS**(`osascript`、本机 Word 转 PDF),自定义非商用许可。四个多月没推送,选择器可能已漂。当参考,不当依赖。 |
| [MarsBobby/TalentCrawler-51job](https://github.com/MarsBobby/TalentCrawler-51job) | Selenium 多城市采集 → 清洗 → 图 | 1★ / 2026-07-01 | 课设。README 写了「失败重试与**仿真数据降级**」:跑挂了会造假数据。不能当生产源。 |
| [Zhousy236/51job-crawler-code](https://github.com/Zhousy236/51job-crawler-code) / [hlman1/51job-crawler](https://github.com/hlman1/51job-crawler) / [yamadia/51job_crawler](https://github.com/yamadia/51job_crawler) | Selenium / Scrapy 练习 | 0★ / 2025-07～2026-06 | 无文档或纯作业。忽略。 |
| [chenjiandongx/51job-spider](https://github.com/chenjiandongx/51job-spider) | Scrapy | **426★** / **2018-06-06** | 中文圈最有名的 51job 爬虫,停更 8 年。star 是历史,不是可用性。 |
| [Bvbrutal/51job-reverse-crawler](https://github.com/Bvbrutal/51job-reverse-crawler) | 前端 JS 逆向 | 3★ / 2023-11-08 | 签名一年一换。2023 的逆向对 2026 的站没有价值。 |
| [hypier/scrapy-51job](https://github.com/hypier/scrapy-51job) | Scrapy + Redis + crawlab | 18★ / 2020-09-10 | 见 jd-collection:选择器失效,只留调度思路。 |

取舍:51job 没有「还能 pip 进来就跑」的库。AgentMesh 和职位猎人插件证明 `we.51job.com` 这条面还活着。老 426★ 仓可以直接当不存在。

---

## 3. 猎聘

搜索页是 `https://www.liepin.com/zhaopin`。现网城市路由已从数字码迁到 `/city-<slug>/zhaopin/`(AgentMesh README 2026-08 仍在写这套校验)。招聘者端是另一张皮:`lpt.liepin.com`。

| 项目 | 路线 | ★ / 最近推送 | 可用性 |
| --- | --- | --- | --- |
| AgentMesh-JobAgent | `jobagent liepin login/discover`;`platforms/liepin/`;夹具 `live_snapshot_real_shape_20260612.json` | 同上 / 2026-08-28 | **求职端还活。** 城市码失效时先读当前结果页官方链接,再回退目录;必须看到真实路由变化才采集。比智联安静,但模块和测试都在。 |
| lastsunday/job-hunting | 插件;`liepin.com/zhaopin`,「需点击搜索按钮才有效果」 | 同上 | 列在支持表。作者自己标了交互限制,说明列表不是打开 URL 就有数据。 |
| Auto-JobHunter | `liepin_scraper/` + cookie harvester | 73★ / 2026-04-27 | 和 51job 同一套。可能还能跑,许可和 macOS 绑定同上。 |
| [Viy1204/liepin-cli](https://github.com/Viy1204/liepin-cli) | Puppeteer/CDP 打 **招聘者端**(`lpt.liepin.com`):搜人、打招呼、简历 | 12★ / **2026-08-25** | **活,但方向反了。** 这是猎头工具,不是 JD 采集。README 自己说公开页抓取不该用它。 |
| [RAYNLIU2005/-Multi-threadedCrawler](https://github.com/RAYNLIU2005/-Multi-threadedCrawler) | DrissionPage/Chromium;`source/liepin.py`;文档里写数据包监听 | 2★ / 2025-10-26 | 分层(`source/controller/sink` + fingerprint)仍是本项目最贴的骨架。10 个月没推,猎聘接口路径会变,当骨架不当时钟。 |
| [silie666/job-crawler](https://github.com/silie666/job-crawler) | Go HTTP,城市/关键词码 | 16★ / 2024-04-24 | 无登录 cookie 项(和智联不同)。2024 的查询参数对现在的 slug 路由,**大概率失效**。 |
| [SomethingCsx/Py_liepin_jobname_spider](https://github.com/SomethingCsx/Py_liepin_jobname_spider) | requests | 0★ / 2026-04-21 | 日期新,路线旧。纯 HTTP 打猎聘,2026 年很难过。 |
| [seew321123/liepin](https://github.com/seew321123/liepin) / [ChoungJX/Liepin-spider](https://github.com/ChoungJX/Liepin-spider) 等 | Scrapy / requests | 0–2★ / 2018–2020 | 坟场。 |

取舍:猎聘求职端跟智联同一套「真实会话」。`liepin-cli` 别误收进采集候选。RAYNLIU 的 `source/liepin.py` 只抄结构。

---

## 4. 跨站合集(一次看三站)

| 项目 | 覆盖 | ★ / 最近推送 | 可用性 |
| --- | --- | --- | --- |
| AgentMesh-JobAgent | 智联 / 51job / 猎聘 / BOSS,平台隔离 | 35★ / 2026-08-28 | 唯一还在按站点修选择器、还带 headed gate 的开源客户端。 |
| lastsunday/job-hunting | 上四者 + 拉勾 + 就业在线 + 广东公共招聘 | 423★ / 扩展 2026-06-30 | 最成熟的消费级工具。插件 + 可选 Rust 服务端。禁止商用(README)。 |
| Auto-JobHunter | BOSS / 51job / 猎聘,无智联 | 73★ / 2026-04-27 | 采集+评估+投递一体。非商用,绑 Mac。 |
| RAYNLIU Multi-threadedCrawler | 四站,`source/*.py` | 2★ / 2025-10-26 | **抄分层,不跑原仓。** |
| [mergedao/mcp-jobs](https://github.com/mergedao/mcp-jobs) | README 称猎聘/BOSS/智联/51job | 125★ / 2026-06-17 | Playwright + cheerio,默认 headless,URL 写的是各站首页(`zhaopin.com/`、`51job.com/`)。零配置营销。对这三站会撞登录墙和验证码。**不要当数据源。** |
| silie666/job-crawler | 四站 | 16★ / 2024-04 | cookie HTTP。过期。 |
| [igaozp/JobWitcher](https://github.com/igaozp/JobWitcher) / hypier/scrapy-51job / [yuyong513/spider2](https://github.com/yuyong513/spider2) | 五站到三十站 | 0–18★ / 2019–2021 | 见 jd-collection。排除。 |

---

## 5. 官方开放接口

公开检索(2026-08-30)找不到三个站面向第三方的 **JD 列表开放 API**。

- 智联:搜「开放平台」落到官网首页和 2019 年扒接口博客,没有一手开发者文档。
- 51job:只有用户协议和招聘页。企业侧对接走销售,不公开。
- 猎聘:有招聘者端自动化([liepin-cli](https://github.com/Viy1204/liepin-cli)、站点上的 CLI/MCP 说明),对象是候选人不是职位列表。

结论:要 JD,只能走已登录会话或买商业库(经管之家/马克数据那批 2016–2025 智联库,见 jd-collection)。没有「申请个 key 就拉全量」的路。

---

## 6. 对本项目的取舍

1. **不 vendor 任何上述仓库。** AgentMesh 要云端 key 和受管 Chrome 画像;职位猎人是插件;Auto-JobHunter 许可和 OS 都不对。
2. **冷启动不动这三站。** `data/` 里已有多份本地 JD,足够把抽取和图跑通。天池只补洞。
3. **若赛题演示必须现场源:** 自写 Playwright,`headless=False` 或持久化 user data dir,`wait_for_response` 拦 JSON。每个站一个 `source`,互不影响。智联城市跳转抄 AgentMesh 的「失败即停、不信单独 URL 参数」;猎聘城市用 slug 路由而不是旧数字码;51job 只认 `we.51job.com`。
4. **骨架继续抄 RAYNLIU** 的 `source/controller/sink` + fingerprint,不要抄它 2025-10 的选择器。
5. **排除:** mcp-jobs、silie666 cookie 重放、426★ 的 2018 年 51job、一切「JS 逆向」教学仓。

和 jd-collection 第 5 节一致:ATS + NCSS 做稳定公开主力,这三站是高价值高风险增量。这次复核只是把「猎聘/智联同样走 Playwright」从一句口号落成可核对的仓库清单。
