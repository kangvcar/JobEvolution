# 调研:技能本体标准与同类产品借鉴

> 对应工单:[#6 调研:技能本体标准与同类产品借鉴](https://github.com/kangvcar/JobEvolution/issues/6)(Part of #1)
> 调研日期:2026-08-28。所有事实均核对官方一手来源(官网、官方下载页、GitHub 仓库),链接见各节与文末。

## 太长不看(TL;DR)

- **图谱底座推荐:ESCO 结构 + O*NET 技术技能数据做冷启动种子,大典 2022 做中文职业名对齐层。** ESCO 提供职业—技能关系骨架和 RDF 原生格式(免费下载,28 种语言但无中文);O*NET 的 Technology Skills 表提供最接近"技能点"颗粒度的技术技能数据(CC BY 4.0,可自由改编);中国职业分类大典提供中文规范职业名,但只到"职业"层、无技能层、无官方开放数据,需自行数字化。
- **Lightcast Open Skills 已不可作为数据底座**:2026 年 2 月起免费 API 转为合同制,仅剩非营利公益通道(每月 50 次调用);其 3.4 万+ 技能库仍可网页浏览,可作技能命名与三层分类的设计参考。
- **竞品最值得抄的四个点**(均直接服务求职者第一用户):roadmap.sh 的交互式技能树 + 进度打卡;My Next Move 的"测评 → 职业推荐 → 前景/热门技术标注"闭环;Lightcast Skills Extractor 的"粘贴简历 → 抽取标准化技能";Tabiya Compass 的对话式技能挖掘 + 技能钱包。

---

## 一、岗位/技能本体对比

### 1. ESCO(欧盟技能、能力、资历与职业分类)

来源:[ESCO 官网 What is ESCO](https://esco.ec.europa.eu/en/about-esco/what-esco)、[下载页](https://esco.ec.europa.eu/en/use-esco/download)、[技能支柱](https://esco.ec.europa.eu/en/classification/skill_main)。

- **规模与结构**:当前版本 v1.2.1,含 **3,039 个职业 + 13,939 项技能**。职业支柱建于 ILO 的 ISCO-08 分类之上(见 [Tabiya 对 ESCO 的说明](https://docs.tabiya.org/our-tech-stack/inclusive-livelihoods-taxonomy/why-esco));技能支柱分四个子分类:**知识(Knowledge)、语言技能、技能(Skills)、可迁移技能(Transversal)**,每个概念带首选术语 + 非首选术语、描述、范围说明、复用级别(transversal / cross-sectoral / sector-specific / occupation-specific)以及与职业和其他技能的关系。技能条目还带 **DigComp / Digital / Green / Research 标签**,便于筛出数字技能子集。
- **技能颗粒度**:细到具体编程语言和工具(可在[技能支柱门户](https://esco.ec.europa.eu/en/classification/skill_main)按 Digital 标签检索验证),接近本项目的"技能点"级。
- **数据下载与授权**:**免费下载**,格式含 CSV、ODS、RDF、TTL、XML、JSON-LD,另提供语义模型(RDF/OWL/SKOS)、Web API 和可本地部署的 Local API;下载流程只需接受隐私声明并留邮箱。版本间提供 delta 文件,便于跟进演化——这与赛题"动态演化"要求契合。
- **中文适配**:官方支持 28 种语言(24 种欧盟官方语言 + 冰岛语、挪威语、乌克兰语、阿拉伯语),**无中文**,需自行翻译技能名并与中文招聘语料对齐。
- **结论**:结构、关系、格式(RDF 原生适配知识图谱)和授权都最适合当图谱骨架;主要成本在翻译与中文对齐。

### 2. O*NET(美国劳工部职业信息网络)

来源:[O*NET Database](https://www.onetcenter.org/database.html)、[31.0 数据库授权页](https://www.onetcenter.org/license_db.html)、[Skills 数据字典](https://www.onetcenter.org/dictionary/30.0/excel/skills.html)、[Technology Skills 数据字典](https://www.onetcenter.org/dictionary/28.3/excel/technology_skills.html)、[My Next Move](https://www.mynextmove.org/help/about/)。

- **规模与结构**:当前版本 31.0,覆盖 900+ 职业(O*NET-SOC 分类)。核心是 **Content Model**:每个职业对通用技能/知识/能力条目按量表打分(如 Skills 文件 6 万+ 行"职业 × 技能 × 量表评分",含样本量、置信区间等统计元数据)——这是"岗位对技能的需求强度"最成熟的量化范式。
- **技术技能点(对本项目最有价值)**:**Technology Skills 文件**收录 3.2 万+ 行"职业 → 具体软件/技术"(如 Adobe Acrobat、具体框架),用 UNSPSC 商品编码归类,并带 **Hot Technology(全市场招聘高频)与 In Demand(该职业招聘高频)** 两个热度标记——直接可用作四领域技术技能点种子与"热门技能"信号。
- **数据下载与授权**:整库免费下载(Excel/CSV/JSON/SQL),**另有官方 RDF 知识图谱版**;授权为 **CC BY 4.0**,明确允许复制与改编,只需署名并声明修改。这是三者中授权最宽松、法律上最省心的。
- **中文适配**:仅英文,职业体系是美国 SOC,与国内岗位命名差异大;建议只取其"技能点 + 热度信号 + 打分范式",不搬其职业层。
- **结论**:不当骨架,当**数据燃料**——技术技能点清单、热度标签和"重要性/水平"打分模式都值得直接复用。

### 3. 中华人民共和国职业分类大典(2022 年版)

来源:[人社部颁布通知(人社部发〔2022〕68号)](http://rsj.shannan.gov.cn/zwgk/zcfg/rsrc/202304/t20230421_118929.html)、[人社部公示公告](http://114.255.111.180/xxgk2020/fdzdgknr/jcgk/zqyj/202207/t20220712_457477.html)、[发布会报道](https://www.jiemian.com/article/8142346.html)。

- **规模与结构**:**8 个大类、79 个中类、449 个小类、1,636 个细类(职业)、2,967 个工种**(公示稿口径;正式颁布后职业数为 1,639)。首次标注 **97 个数字职业(S)**、134 个绿色职业(L)。层级只到"职业/工种",**没有技能层**;技能要求散见于各职业的《国家职业标准》,以文件形式逐职业发布,非结构化数据。
- **数据可得性与授权**:以图书出版 + 官方查询系统提供,**无官方开放结构化下载**;作为国家规范文件引用职业名称与编码无授权障碍,但全文数字化需自行录入或购买出版物。
- **中文适配**:中文原生,且"数字职业"标注与赛题四领域高度相关(如"数字技术工程技术人员"小类下含人工智能、大数据、物联网相关职业)。
- **结论**:不能当技能图谱底座,但**必须作为中文职业名称规范层**——图谱的岗位节点对齐大典编码,保证与国内政策、招聘市场话语一致。

### 4. 新加坡 SkillsFuture 技能框架(SFw,补充参考)

来源:[Jobs-Skills Portal 框架下载页](https://jobsandskills.skillsfuture.gov.sg/frameworks/skills-frameworks)、[IMDA ICT 框架职业地图](https://www.imda.gov.sg/-/media/imda/images/programmes/skills-framework-for-ict/consolidated-career-maps.pdf)。

- **结构**:覆盖 38 个行业,**岗位(job role)→ 关键任务 → 技术技能 TSC(带 1–6 熟练等级)+ 通用核心技能 CCS**;ICT 框架含 8 个赛道、33 个子赛道、123 个岗位,并给出岗位间晋升/转岗路径。官方提供 **Skills Framework Dataset、Unique Skills List(跨行业去重技能表)、TSC 映射文件**免费下载。
- **结论**:数据为英文、体量有限,不作底座;但其 **"岗位 → 任务 → 技能 → 熟练级 → 课程"的 schema 是本项目数据模型的最佳模板**,"Unique Skills List + 映射文件"的做法也值得照搬(跨领域技能去重)。

### 本体对比速览

| 维度 | ESCO v1.2.1 | O*NET 31.0 | 大典 2022 | SFw(新加坡) |
|---|---|---|---|---|
| 职业数 | 3,039 | 900+ | 1,639 | 38 行业(ICT 123 岗位) |
| 技能层 | 13,939 项,分四子类 | 量表化条目 + 3.2 万行技术技能 | 无 | TSC + 1–6 熟练级 |
| 技能点颗粒度 | 到具体语言/工具 | 到具体软件/技术(UNSPSC 编码) | — | 到技能项(偏能力单元) |
| 可下载 | 免费,CSV/RDF/TTL/JSON-LD + API | 免费,Excel/CSV/JSON/SQL + RDF 图谱 + API | 无官方结构化数据 | 免费 Excel 数据集 |
| 授权 | 免费使用,接受欧盟条款并署名 | CC BY 4.0(可改编) | 国家规范,无开放数据授权 | 官方免费提供 |
| 中文 | 无(28 语种) | 无 | 原生中文 | 无 |

---

## 二、Lightcast(原 Emsi Burning Glass)Open Skills 现状

来源:[Lightcast Skills Taxonomy 页](https://lightcast.io/open-skills)、[Open Skills FAQ](https://lightcast.io/our-data/taxonomies/open-skills/faqs)、[API 访问文档](https://docs.lightcast.io/lightcast-api/docs/api-access)。

- 技能库规模 **34,000+**,三层结构 **Category → Subcategory → Skill**,每月更新并公开 changelog;全部技能仍可在官网**免费浏览**,并提供 Skills Extractor 网页工具(粘贴 JD/简历/大纲即抽取标准化技能)。
- **免费 API 已于 2026 年 2 月中旬终止**(官方 FAQ 表述为"API access is now available on a contract basis";社区反馈仅提前三天通知,见 [LinkedIn 讨论](https://www.linkedin.com/posts/nick-renner_skillstaxonomy-workforceintelligence-opendata-activity-7431704170384109568-jwkK))。目前仅剩**非营利公益免费通道**:限 `lightcast_open_free` 范围、每月 50 次技能抽取调用,需申请审批,不可用于生产规模。
- **结论**:不可依赖其作为数据底座或线上服务;其三层技能分类法、"月度更新 + 公开 changelog"的演化治理方式、以及 Skills Extractor 的交互形态,是设计参考。

---

## 三、本体复用建议(推荐方案)

**分层复用,四领域裁剪:**

1. **骨架层 = ESCO**:用 ESCO 的"职业—技能"关系模型与 RDF/SKOS 语义模型定义图谱 schema;按 Digital/DigComp 标签 + ICT 相关职业组裁出 AI/大数据/智能系统/物联网四领域子集作冷启动。用 delta 文件机制跟踪版本演化。
2. **技能点数据层 = O*NET Technology Skills**:导入其"职业 → 具体技术"三万余行数据与 Hot Technology / In Demand 标记,补足 ESCO 在具体工具/框架层的覆盖;沿用其"重要性/水平"双量表为岗位—技能边赋权。CC BY 4.0,合规成本最低,只需署名。
3. **中文规范层 = 大典 2022**:岗位节点挂大典职业编码与规范中文名(优先 97 个数字职业相关小类);技能名中文化依靠"人工翻译核心集 + 国内招聘语料对齐扩展"。
4. **schema 模板 = SkillsFuture SFw**:借用"岗位 → 任务 → 技能点 → 熟练等级(1–6)→ 学习资源"结构,支撑"差距分析 → 学习路径"功能;借用 Unique Skills List 思路做跨领域技能去重。
5. **工程捷径 = Tabiya 开源栈**:[Tabiya](https://docs.tabiya.org/our-tech-stack/inclusive-livelihoods-taxonomy/why-esco) 已验证"以 ESCO 为底、本地化扩展"路线,其[开放本体平台](https://github.com/tabiya-tech/taxonomy-model-application)(MIT)、[ESCO 数据集与工具](https://github.com/tabiya-tech/tabiya-esco-datasets-and-tools)(MIT)、Core Taxonomy(CC BY 4.0,CSV 分发)可直接复用其数据模型与管理工具,省去自建本体管理平台。

**不推荐**:Lightcast 作数据源(商业闭源化);大典作技能层(无技能数据);从零自建本体(冷启动成本高且无对齐锚点)。

---

## 四、竞品功能借鉴清单

标注 ✦ 的条目直接服务本项目第一用户(求职者:上传简历 → 图谱定位 → 差距分析 → 学习路径)。

| 产品 | 类型 | 值得借鉴的功能/交互 | 服务求职者 |
|---|---|---|---|
| [roadmap.sh / developer-roadmap](https://github.com/kamranahmedse/developer-roadmap)(GitHub 36.5 万+ star) | 开源 | **交互式技能树**:按角色(AI 工程师、数据分析师等)组织的可点击路线图,节点展开学习资源;**进度打卡**(done/skip)形成个人完成度;AI 生成个性化 roadmap;社区共建更新 | ✦ 图谱可视化与学习路径的交互范本 |
| [My Next Move](https://www.mynextmove.org/help/about/)(O*NET 官方求职者门户) | 政府/公益 | **兴趣测评(RIASEC 30 题)→ 职业推荐**的低门槛入口;职业页整合任务、技能、薪资、**Bright Outlook 前景标记**、**Hot Technology 火焰图标**;按行业/关键词/测评三种找职业方式 | ✦ "不知道自己适合什么"的冷启动交互 |
| [Lightcast Skills Extractor](https://lightcast.io/open-skills) | 商业 | **粘贴简历/JD/课程大纲 → 实时抽取标准化技能**,即时给用户"我有哪些可命名的技能"反馈 | ✦ 正是"上传简历 → 图谱定位"环节的成熟形态 |
| [Tabiya Compass](https://github.com/tabiya-tech/compass)(MIT) | 开源 | **AI 对话式技能挖掘**:通过聊天从正式/非正式经历中发现技能,沉淀为"数字技能钱包";适合简历信息稀疏的求职者 | ✦ 简历解析的补充:对话补全经历 |
| [SkillsFuture Jobs-Skills Portal](https://jobsandskills.skillsfuture.gov.sg/frameworks/skills-frameworks) | 政府 | **交互式技能框架**:按岗位/技能/行业三种视角浏览;岗位页直接给出 TSC 熟练等级要求并**映射到可报名课程**;职业晋升路径图 | ✦ "差距分析 → 学习路径 → 课程"闭环范本 |
| [O*NET OnLine / RDF 知识图谱](https://www.onetcenter.org/database.html) | 政府 | 官方以 RDF 知识图谱形式发布本体数据;Hot/In-Demand 技术每期随招聘数据更新——"图谱 + 劳动力市场信号"的动态演化机制 | 面向开发者/分析师(间接惠及求职者) |
| [Lightcast 技能库治理](https://lightcast.io/our-data/taxonomies/open-skills/faqs) | 商业 | **月度版本 + 公开 changelog + 社区技能建议论坛**的本体演化治理流程 | 面向平台方(保证图谱鲜度) |

**功能优先级建议**(按求职者旅程):① 简历/文本技能抽取(抄 Skills Extractor,兜底用 Compass 式对话补全)→ ② 技能树可视化 + 完成度标记(抄 roadmap.sh)→ ③ 目标岗位差距对比(抄 SFw 的 TSC 等级差)→ ④ 学习路径与资源映射(抄 SFw 课程映射 + roadmap.sh 节点资源)→ ⑤ 热门技能信号(抄 O*NET Hot Technology)。

---

## 附:关键链接汇总

- ESCO:官网 <https://esco.ec.europa.eu/en/about-esco/what-esco> · 下载 <https://esco.ec.europa.eu/en/use-esco/download> · 技能支柱 <https://esco.ec.europa.eu/en/classification/skill_main>
- O*NET:数据库 <https://www.onetcenter.org/database.html> · 授权 <https://www.onetcenter.org/license_db.html> · My Next Move <https://www.mynextmove.org>
- 大典 2022:颁布通知 <http://rsj.shannan.gov.cn/zwgk/zcfg/rsrc/202304/t20230421_118929.html> · 公示公告 <http://114.255.111.180/xxgk2020/fdzdgknr/jcgk/zqyj/202207/t20220712_457477.html>
- SkillsFuture:框架与数据集下载 <https://jobsandskills.skillsfuture.gov.sg/frameworks/skills-frameworks>
- Lightcast:技能库 <https://lightcast.io/open-skills> · FAQ <https://lightcast.io/our-data/taxonomies/open-skills/faqs> · API 访问 <https://docs.lightcast.io/lightcast-api/docs/api-access>
- 开源项目:developer-roadmap <https://github.com/kamranahmedse/developer-roadmap> · Tabiya 本体平台 <https://github.com/tabiya-tech/taxonomy-model-application> · Tabiya Compass <https://github.com/tabiya-tech/compass>
