# 调研:公司官网招聘页开源采集

> **档案。** 定案以 `docs/product.md`、`docs/tech.md` 为准。招聘平台(BOSS/智联/猎聘)仍见 `docs/research/jd-collection.md` 与 `docs/research/job-site-crawlers.md`。本文只覆盖**公司自己的 careers 门户**。
> 合规:只做技术可行性判断,不做法律背书。本文不写绕过登录墙、验证码或可用 payload。
> 核查时间:2026-09-03。star / 推送会变,装之前打开仓库页。
> 可用性口径:看仓库最近提交、README 声明的端点、以及本机对公开 JSON 的一次轻量探测。**没有对全部公司实跑全量**,下表是仓库证据加抽检,不是「我把 170 家都跑通了」。

## 0. 一句话结论

有开源项目,而且分成两套几乎不相交的世界。

海外科技公司的官网招聘页,背后多半是 Greenhouse / Lever / Ashby / Workday,公开 JSON,2026 年有可 `pip install` 的库。国内互联网公司走自建门户或飞书招聘 / Moka / 北森。真正对口、还在推的是 [simonlin1212/Hiring-Radar](https://github.com/simonlin1212/Hiring-Radar)(飞书/Moka/北森通用解析 + 腾讯/字节/网易/京东/百度自建)和 [he-yufeng/FindJobs-Agent](https://github.com/he-yufeng/FindJobs-Agent)(二十多家国内大厂,JSON 优先,阿里/美团/京东走 Selenium)。[Nanaeo/RecruitSpider](https://github.com/Nanaeo/RecruitSpider) 标题最贴「各个互联网企业的招聘网站爬虫」,但 2023-12 停更,只能当端点考古。

本项目不要 vendor 上述仓库。若试官网源,自写 `source`,端点形状抄 Hiring-Radar / FindJobs-Agent,分层仍抄现有 `source/controller/sink`。先打已验证的公开 JSON(腾讯、字节、飞书门户),不要先碰阿里/美团的 Selenium。

---

## 1. 官网招聘页不是一个站

国内互联网公司的「官方招聘页」通常落在三类系统上。一类系统写一个解析器,加公司只加配置。自建门户一家一个。

| 类型 | 典型域名 | 取数方式 | 覆盖谁 |
| --- | --- | --- | --- |
| 飞书招聘 | `{slug}.jobs.feishu.cn` | `POST /api/v1/search/job/posts`,头里带 `website-path` | 智谱 / MiniMax / 月之暗面 / 理想 / 蔚来 / 米哈游 等。Hiring-Radar 种子表 73 条飞书行 |
| Moka | `app.mokahr.com/social-recruitment/{org}/{site}` | 列表 JSON;部分租户 AES-CBC 信封,密钥在前端公开字段里 | 寒武纪 / 鹰角 / SHEIN 等。Hiring-Radar 79 条;ats-scrapers 也有 `moka.py` |
| 北森 | `{slug}.zhiye.com` | `POST /api/Jobad/GetJobAdPageList` | 追觅 / 奇瑞 等制造与车企偏多。Hiring-Radar 5 条;ats-scrapers 有 `beisen.py` |
| 大厂自建 | `careers.tencent.com`、`jobs.bytedance.com`、`talent.alibaba.com`、`zhaopin.meituan.com`… | 各家前端自己打的搜索 JSON,或 SPA 空壳要浏览器 | 腾讯/字节/网易/京东/百度 JSON 还能打;阿里/美团开源实现常退到 Selenium |
| 海外 ATS | `boards.greenhouse.io`、`jobs.lever.co`、`jobs.ashbyhq.com` | 无 key 的公开 boards API | Stripe / Anthropic / OpenAI 这类。国内 BAT 几乎不用 |

飞书开放平台的 [获取职位列表](https://open.feishu.cn/document/ukTMukTMukTM/uMzM1YjLzMTN24yMzUjN/hire-v1/job/list) 要租户 `tenant_access_token`,是雇主自己的应用,不是外人扫门户的路。开源项目读的是门户前端那条匿名 JSON。

---

## 2. 国内官网:值得看的仓库

star / 最近推送取自 GitHub API,2026-09-03。

| 项目 | 覆盖 | ★ / 最近推送 | 许可 | 可用性 |
| --- | --- | --- | --- | --- |
| [simonlin1212/Hiring-Radar](https://github.com/simonlin1212/Hiring-Radar) | 飞书/Moka/北森通用 + 腾讯/网易/京东/百度/字节/宇树自建;种子表约 170 家 | 22★ / **2026-09-01** | MIT | **国内官网最对口。** 单入口 `hiring_radar.py`,核心纯标准库,Moka 才要 `pycryptodome`。加公司=往 `parsers/companies.seed` 加一行。README 写明只读公开接口、不绕登录。本机抽检:腾讯、字节、飞书智谱门户的搜索 JSON 仍返回岗位 |
| [he-yufeng/FindJobs-Agent](https://github.com/he-yufeng/FindJobs-Agent) | `job_crawler_v2.py` 的 `CRAWLERS`:腾讯/网易/字节 JSON;阿里/美团/京东 Selenium;再加百度/快手/小米/B 站/滴滴/拼多多/华为/携程/大疆/蔚来/小鹏/理想/OPPO/vivo/商汤,以及若干飞书门户;另有智联/拉勾和外企 | 252★ / **2026-09-02** | MIT | **国内大厂名单最全。** 是求职 Agent(抽取、简历匹配、模拟面试),不是采集库。代码把阿里/美团/京东标成 Selenium「增强抗反爬」。不要整仓引入,可抄公司→URL 对照 |
| [kalil0321/ats-scrapers](https://github.com/kalil0321/ats-scrapers) | pip 包。海外 ATS 为主,源码里已有 `bytedance.py`、`moka.py`、`beisen.py`;**没有** `feishu.py`、**没有**腾讯 | 147★ / **2026-09-02** | MIT | 可 `pip install ats-scrapers`。字节适配器打的是 `jobs.bytedance.com/api/v1/public/supplier/search/job/posts`(joinbytedance.com 英文门户),和国内社招搜索不是同一条。一期不必装这个包 |
| [Nanaeo/RecruitSpider](https://github.com/Nanaeo/RecruitSpider) | 腾讯/阿里系(菜鸟/饿了么/高德/阿里云/淘天)/美团/字节/百度/网易/知乎,每家一个 `.py` | 6★ / **2023-12-18** | 无 LICENSE | 标题就是用户问的事。脚本是教学级:`pageSize=9999`、打印不入库。腾讯那条 `tencentcareer/api/post/Query` 2026-09-03 仍活;阿里 CSRF、字节 csrf token 路径能参考,选择器和域名会漂 |
| [shuheng-mo/career-ops-china](https://github.com/shuheng-mo/career-ops-china) | 预置 50+ 公司 careers URL,含字节/阿里/腾讯 | 92★ / **2026-09-03** | MIT | **明确放弃自动化爬国内大厂 SPA。** README 写 Playwright/WebFetch 失败率高,主路径改成 bookmarklet 人机协作。证明「官网页」和「官网 JSON」不是一回事 |
| [brantou/crawler](https://github.com/brantou/crawler) | README 列阿里/百度/美团/滴滴 | 107★ / **2017-09-19** | MIT | 坟场。star 是历史 |
| [Meterprete/Tencent-recruitment-crawler](https://github.com/Meterprete/Tencent-recruitment-crawler) | 只腾讯,Scrapy | 0★ / 2020-03-21 | 无 | 教学文,端点与 Hiring-Radar 同源,无维护 |

秋招信息聚合仓(如 [xixicc186/xixicc2027](https://github.com/xixicc186/xixicc2027))是网申链接和公众号入口的人工表,不是岗位正文采集器。

### Hiring-Radar 自建端点(源码)

仓库 `parsers/` 里写死的 URL,可直接当对照:

- 腾讯 `GET https://careers.tencent.com/tencentcareer/api/post/Query`
- 字节 `POST https://jobs.bytedance.com/api/v1/search/job/posts`
- 飞书 `{host}/api/v1/search/job/posts`
- 北森 `{slug}.zhiye.com/api/Jobad/GetJobAdPageList`
- Moka `{host}/api/outer/ats-apply/website/jobs/v2`

FindJobs-Agent 另有一批大厂 URL,仓库里自己标了「已验证可用 (API)」的是腾讯/网易/字节;阿里/美团/京东走 Selenium。百度 `talent.baidu.com/httservice/getPostListNew`、网易 `hr.163.com/api/hr163/position/queryPage`、快手 `zhaopin.kuaishou.cn/recruit/api/job/list` 等只在源码里出现,本文未逐个探测。

---

## 3. 海外 ATS:官网页的另一条路

国内 BAT 基本不在这条路上。外企在华、出海岗位、英文对照才用得上。`docs/research.md` 已把 Greenhouse / Lever / Ashby 列为稳定公开源,这里补 2026 年还活的实现。

| 项目 | 做什么 | ★ / 最近推送 | 对本项目 |
| --- | --- | --- | --- |
| [kalil0321/ats-scrapers](https://github.com/kalil0321/ats-scrapers) | pip 库 + 托管数据集。`get_scraper_for_url("https://jobs.ashbyhq.com/openai")` | 147★ / 2026-09-02 | 抄端点,不装一期依赖 |
| [noble-ronin/ats-job-apis](https://github.com/noble-ronin/ats-job-apis) | 公开 boards 端点速查:Greenhouse / Lever / Ashby / Workday / SmartRecruiters… | 2★ / 2026-07-25 | **先读这个再写 source。** 例如 Greenhouse `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` |
| [strelov1/freehire](https://github.com/strelov1/freehire) | 92 个 ATS + 部分公司直连,公开站点 [freehire.me](https://freehire.me) | 570★ / 2026-09-02 | 聚合成品。FindJobs-Agent 已把它当可选源。不要把对方全站当本项目后端 |
| [elliottdehn/open-jobs](https://github.com/elliottdehn/open-jobs) | 约 2M 条、25 个 ATS、CC0 快照 | 123★ / 2026-09-03 | 英文语料,可当抽取对照,不是国内官网增量 |
| [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator) | GH Actions 日更 Greenhouse/Lever/Ashby/Workday 等 | 140★ / 2026-09-02 | 调度思路可看,覆盖仍是海外 |
| [datascry/openroles](https://github.com/datascry/openroles) | 51 个 ATS,GitHub Pages 静态板;另有 Amazon/Apple/TikTok/Meta 直连 | 5★ / 2026-08-31 | TikTok 直连和字节国内社招不是同一套 |
| [Babak-hasani/company-career-scraper](https://github.com/Babak-hasani/company-career-scraper) | 169 家 GH/Lever/Ashby/SmartRecruiters → CSV | 3★ / 2026-03-29 | 小脚本,公司名单写死 |

Greenhouse 抽检(2026-09-03):`boards-api.greenhouse.io/v1/boards/stripe/jobs` 返回 592 条,无需登录。

---

## 4. 本机抽检(2026-09-03,各 2 条,只打列表)

| 源 | 结果 |
| --- | --- |
| 腾讯 `tencentcareer/api/post/Query?pageSize=2` | `Code=200`,`Count=2269`,标题如「《英雄联盟手游》-研发项目经理」 |
| 字节 `jobs.bytedance.com/api/v1/search/job/posts` | `code=0`,列表有「商业分析师…抖音搜索」「大模型推荐算法工程师…TikTok算法」。裸 POST 即可;RecruitSpider 那套 csrf token 不是硬前置 |
| 飞书 `zhipu-ai.jobs.feishu.cn/api/v1/search/job/posts` + `website-path: index` | `code=0`,标题如「解决方案架构师-北京」。门户首页 404,搜索接口仍通。Hiring-Radar 靠首页 `js-websiteInfo` 探 path,首页挂了要回退候选 path |
| 飞书 `moonshot.jobs.feishu.cn/` | 首页 404。种子表会过期 |
| Greenhouse Stripe | 592 条 |

没有对阿里、美团、Moka、北森做同样抽检。FindJobs-Agent 把前两家标成 Selenium,Moka 有加密信封,这两类成本高于腾讯/字节/飞书。

---

## 5. 对本项目的取舍

和 `docs/tech.md` 采集分层一致:官网源是 `source=ats`(或日后拆 `feishu` / `tencent`),不是 `playwright` 那条高风险增量。

1. **不 vendor。** Hiring-Radar 是个人求职雷达;FindJobs-Agent 绑 LLM 面试和前端;ats-scrapers 还带托管数据集。本项目只要统一记录(公司、岗位名、正文、发布日、渠道)。
2. **若只是「试试」,先打三条已验证 JSON。** 腾讯 Query、字节 search/job/posts、一家飞书门户(智谱这种)。字段映射进现有 `collectors/source.py`,fingerprint 仍 `sha256(source + job_id)`。
3. **加公司优先加飞书/Moka/北森配置,而不是每家写爬虫。** Hiring-Radar 的 `companies.seed` 就是这个模型。国内 AI 公司大量在飞书招聘上。
4. **阿里/美团/京东官网不要当第一批。** 开源实现已经退到 headed 浏览器。要这三家,现有结论仍是 Playwright 会话,和 BOSS 一条风险带。
5. **海外 ATS 继续按 `docs/research.md` 抄端点,不装 ats-scrapers。** 对国内四领域覆盖帮助有限。
6. **排除。** RecruitSpider 当依赖;career-ops-china 的 bookmarklet 当采集 worker;2017 的 brantou/crawler;把 freehire 全站当数据源(对方 ToS 和新鲜度都不在我们控制里)。

冷启动仍然是仓库 `data/` 本地 JD。官网源是增量实验,不挡现有管线。
)
