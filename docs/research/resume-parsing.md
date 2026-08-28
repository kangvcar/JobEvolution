# 调研:简历解析开源实现与准确率基准

> 对应工单:[#4 调研:简历解析开源实现与准确率基准](https://github.com/kangvcar/JobEvolution/issues/4)(Part of #1)
> 调研日期:2026-08-28
> 场景约束:中文简历为主(PDF/Word),提取技能要素,准确率目标 ≥90%,LLM 使用 DeepSeek 官方 API。

## 一、结论速览

1. **"PDF/Word 转文本 + LLM 结构化抽取"是当前准确率最高的路线**,字段级 F1 可达 0.92–0.96;纯规则/NER 路线(如商业系统 Bello、PaddleNLP)F1 只有 0.49–0.82,达不到 90% 目标。数据来源:阿里巴巴 SmartResume 论文([arXiv:2510.09722](https://arxiv.org/abs/2510.09722),系统已在阿里 HR 平台生产部署)。
2. **DeepSeek 模型可以胜任**:在 SmartResume 的版面感知管线中,DeepSeek-v3 零样本即达到字段级 F1 0.950(合成中文简历集)/ 0.944(真实简历集),与 GPT-4o、Claude-4 同一档位。
3. **版面感知(layout-aware)预处理是从 ~92% 提到 ~96% 的关键**:约 20% 简历是双栏等非线性版式,直接线性抽文本会打乱阅读顺序。但对我们"技能要素提取"这个子任务,90% 目标用"文本层直读 + LLM"即可先达标,版面感知可作二期优化。
4. **准确率度量业界通行做法是字段级 Precision/Recall/F1**(先用匈牙利算法做实体对齐,再逐字段多策略匹配);技能提取应按"技能项集合"算 set-based P/R/F1。没有公开的中文"整简历解析"权威基准,最接近的是 SmartResume 随论文发布的 SynthResume/RealResume,以及序列标注口径的中文 Resume NER 数据集(Zhang & Yang, ACL 2018)。

## 二、开源项目清单

### 2.1 重点:SmartResume(阿里巴巴)——首选参考实现

- 仓库:[alibaba/SmartResume](https://github.com/alibaba/SmartResume)(Apache-2.0,Python,2025-11 开源,2026-06 仍有提交)
- 论文:[Layout-Aware Parsing Meets Efficient LLMs (arXiv:2510.09722)](https://arxiv.org/abs/2510.09722)
- 架构:OCR + PDF 元数据融合取文本 → 版面检测重建阅读顺序(输出带行号的线性文本)→ LLM 分三个并行子任务抽取(基本信息 / 工作经历 / 教育经历),长文本字段用"行号指针"而非生成原文,避免幻觉且省 token → JSON 输出。
- 官方指标:信息抽取整体准确率 93.1%,版面检测 mAP@0.5 92.1%,单页 1.22s;生产环境吞吐 240–300 份/分钟,平均时延 1.54s/份。
- 中文支持:第一优先语言(训练与评测集以中文为主),README 有中文版。
- 注意:开源版为合规重构版,内部 PDF 解析与 OCR 组件被开源替代品换掉,部分能力打折;LLM 可接远程 API(兼容 OpenAI 格式,可指向 DeepSeek)或 vLLM 本地部署。

### 2.2 其他开源项目

| 项目 | 路线 | 中文支持 | 维护状态 | 备注 |
| --- | --- | --- | --- | --- |
| [alibaba/SmartResume](https://github.com/alibaba/SmartResume) | 版面感知 + LLM | ✅ 中文优先 | ✅ 活跃(2026-06) | Apache-2.0,附论文与基准数据集 |
| [srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher) | LLM 解析 + JD 匹配 | 一般(英文为主) | ✅ 活跃 | Apache-2.0,~28k star;侧重简历-岗位匹配而非解析准确率 |
| [liangdabiao/resume-matcher-agent-cn](https://github.com/liangdabiao/resume-matcher-agent-cn) | LLM(OpenAI 兼容 API) | ✅ 中文场景二开 | 较新 | 基于 Resume-Matcher 的中文改造,pdfminer.six 抽文本,明确支持 DeepSeek 等国产 API |
| [liangdabiao/LLM-Agent-Resume](https://github.com/liangdabiao/LLM-Agent-Resume) | LLM 抽取 + 向量检索筛选 | ✅ 中文 | 较新 | 教学型项目,`document_parser.py`/`extractor.py` 模块划分可借鉴 |
| [xitanggg/open-resume](https://github.com/xitanggg/open-resume) | 浏览器端规则解析 | ❌ 英文 ATS 场景 | ✅ 活跃(2026-06) | AGPL-3.0,TypeScript;解析算法文档写得好,但面向英文单栏简历 |
| [Ruthikr/ai-resume-parser](https://github.com/Ruthikr/ai-resume-parser) | LangChain + 多 LLM | 取决于模型 | 活跃 | PyPI 可装,支持 PDF/DOCX/图片;可作接口设计参考 |
| [OmkarPathak/pyresparser](https://github.com/OmkarPathak/pyresparser) | spaCy/NLTK 规则 | ❌ | ❌ 2019 年后停更([deps.dev 维护评分 0/10](https://deps.dev/project/github/omkarpathak%2fpyresparser)) | 老一代代表,不建议使用 |
| [chen0040/keras-chinese-resume-parser-and-analyzer](https://github.com/chen0040/keras-chinese-resume-parser-and-analyzer) | 规则 + CNN/LSTM 行分类 | ✅ 中文 | ❌ 多年未更新 | 历史参考价值:pdfminer.six + python-docx 抽文本、逐行分类的思路 |

商业对照(不采用,仅作准确率锚点):Bello(国内商用简历解析,SmartResume 论文中作为工业基线,真实集 F1 0.817)、合合 TextIn [xparse 简历解析](https://www.textin.com/news/20260624115131492)(版式识别 + 结构化抽取,提供字段坐标溯源)。

**结论:老一代规则/NER 开源解析器(pyresparser 等)全部停更且不支持中文;活跃项目全部转向 LLM 路线。SmartResume 是唯一"中文优先 + 有论文基准 + 生产验证"的开源实现。**

## 三、技术路线对比:LLM 直接解析 vs 规则/版面模型混合

SmartResume 论文 Table 2 给出了同一评测框架下的直接对比(字段级,均值涵盖全部字段;SynthResume 为 2,994 份合成中文简历,RealResume 为 13,100 份阿里真实简历,中英混排、版式复杂):

| 路线 | 代表 | SynthResume F1 | RealResume F1 | 时延/份 |
| --- | --- | --- | --- | --- |
| 规则/NER 混合(商业) | Bello | 0.762 | 0.817 | 1.4–1.6s |
| 规则/NER(开源) | PaddleNLP | 0.523 | 0.492 | ~21s |
| 纯 LLM 直读(OCR 文本直接喂给 Claude-4) | naive LLM | 0.927 | 0.919 | ~21s |
| 版面感知 + LLM(零样本) | DeepSeek-v3 | **0.950** | **0.944** | 8.7–10.6s |
| 版面感知 + LLM(零样本) | Claude-4 / GPT-4o | 0.946–0.952 | 0.954–0.959 | 4.6–6.3s |
| 版面感知 + 微调小模型 | Qwen3-0.6B-SFT | 0.917 | **0.964** | **1.2–1.5s** |

关键解读:

- **规则/NER 路线达不到 90%**:强如商业系统 Bello 也只有 0.82,且长文本字段(工作描述等)F1 仅 0.50;开源 PaddleNLP 方案不到 0.53。
- **LLM 直读已能过 90% 线**(0.919–0.927),版面感知预处理再加 2–4 个点,收益主要在双栏版式和长文本字段(Claude-4 长文本 F1 从 0.548 → 0.854)。
- **成本与速度**:LLM 路线的时延瓶颈在模型推理。DeepSeek API 走 OpenAI 兼容格式,当前主力模型 deepseek-v4-flash(官方说明 `deepseek-chat` 已成为其非思考模式的兼容别名,将弃用),[2026-08-17 起实行峰谷计价](https://www.ithome.com/0/989/418.htm):flash 高峰输入 ¥3/百万 tokens(缓存未命中)、输出 ¥9/百万 tokens,空闲时段减半,周末全天谷价。一份简历约 2,000–3,000 输入 tokens、500–1,000 输出 tokens,**单份解析成本约 ¥0.01–0.02(峰时),批量夜间跑减半**——万份简历量级成本 <¥200,可忽略。
- **速度优化手段**(SmartResume 已验证):按信息类别拆成并行子任务、长文本字段返回行号区间而非原文(省输出 token 且消除改写幻觉)、JSON 输出 + 字符串截取而非受限解码。

### PDF 转文本工具链

| 工具 | 许可 | 特点 | 适用 |
| --- | --- | --- | --- |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | MIT | 基于 pdfminer.six,坐标/表格信息完整,速度较慢(~18 页/s) | 首选:许可宽松,简历页数少,速度无所谓 |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | **AGPL-3.0** | 最快(~180 页/s),容错好 | 商用需注意 AGPL 传染或购买商业许可 |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | MIT | pdfplumber 的底层;resume-matcher-agent-cn 直接用它 | 备选 |
| [marker](https://github.com/datalab-to/marker) / [MinerU](https://github.com/opendatalab/MinerU) / [docling](https://github.com/docling-project/docling) | 开源(marker/MinerU 建议 GPU) | 神经版面模型转 Markdown,阅读顺序/表格还原好 | 二期处理双栏、扫描件时再引入,一期过重 |

Word 解析:`.docx` 用 [python-docx](https://github.com/python-openxml/python-docx)(MIT)按段落/表格取文本即可,Word 是流式格式,没有 PDF 的版面问题;老 `.doc` 建议用 LibreOffice `soffice --convert-to docx` 先转格式。扫描件/图片简历需 OCR(PaddleOCR / RapidOCR),一期可先声明不支持。

> 注:网上流传的 pdfmux 等横评数据出自厂商自建基准([pdfmux.com](https://pdfmux.com/)),仅作参考,上表速度/许可信息以各项目官方仓库为准。

## 四、准确率如何度量

### 4.1 业界口径:字段级 P/R/F1(+ 实体对齐)

SmartResume 论文(§4.1.3、附录 E)给出了目前最完整的可复用定义,也是其开源代码自带的评测框架:

1. **实体对齐**:简历中"工作经历""教育经历"是列表型实体,预测列表与标注列表的顺序、数量都可能不一致。先按关键字段(公司名、职位等)的字符串相似度构造相似矩阵,用**匈牙利算法**做一对一最优对齐。
2. **多策略字段匹配**:对齐后逐字段比较,按字段语义选择匹配规则(日期做归一化比较、名称做模糊匹配、长文本做相似度阈值),而非一刀切精确匹配。
3. **指标**:字段级 Precision / Recall / F1,外加"对齐准确率"(Accuracy,已对齐字段中匹配正确的比例)用于区分对齐误差和匹配误差。

### 4.2 技能项级度量(本项目的核心指标)

技能要素提取本质是"从一份简历得到一个技能集合",建议按 **set-based P/R/F1** 度量:

- 预测技能集 S_pred 与人工标注技能集 S_gold,经**技能词归一化**(同义词映射到统一词条,如 "K8s"→"Kubernetes"、"tf"→"TensorFlow")后求交集;
- Precision = |交集|/|S_pred|,Recall = |交集|/|S_gold|,F1 为调和平均;
- "准确率 ≥90%"建议在验收口径上明确为**技能项级 F1 ≥ 0.90**(单说 accuracy 对集合任务无良定义),同时报告字段级 F1 作为整体解析质量参考。

### 4.3 可用的公开基准/数据集

| 数据集 | 规模/语言 | 口径 | 参考成绩 |
| --- | --- | --- | --- |
| SynthResume(SmartResume 随论文发布) | 2,994 份,中文,15 字段,含非线性版式 | 字段级 P/R/F1 | 最优 F1 0.952(GPT-4o in pipeline) |
| RealResume(论文私有,方法可复用) | 13,100 份真实简历,中英混排,19 字段 | 字段级 P/R/F1 | 最优 F1 0.964(Qwen3-0.6B-SFT) |
| [Chinese Resume NER](https://github.com/jiesutd/LatticeLSTM)(Zhang & Yang, ACL 2018) | ~4.7k 句,中文(新浪财经高管简历) | 实体级(BIO 序列标注)F1 | SOTA 96%+([榜单](https://opencodepapers-b7572d.gitlab.io/benchmarks/chinese-named-entity-recognition-on-resume.html)) |

注意:Resume NER 数据集是**句子级 NER**(人名、机构、职称等 8 类实体),不含技能字段、不含 PDF 版面环节,只能作为中文 NER 组件的参考,不能直接当"简历解析准确率"基准。**没有公开的中文技能项级基准,需要自建。**

## 五、推荐技术路线

一期(达标 90%,最短路径):

1. **文本提取**:PDF 用 pdfplumber(MIT)读文本层;`.docx` 用 python-docx;`.doc` 先经 LibreOffice 转 docx;文本层为空(扫描件)一期直接拒收并提示。
2. **结构化抽取**:DeepSeek API(`deepseek-v4-flash`,JSON Output 模式),按 SmartResume 的做法把抽取拆成 2–3 个并行子任务(基本信息+教育 / 工作与项目经历 / 技能要素),每个子任务用专门 prompt,输出固定 JSON schema。技能抽取 prompt 中内嵌岗位能力图谱的技能词表作为归一化引导。
3. **技能归一化**:LLM 输出后过一层同义词映射表(维护在图谱侧),保证与能力图谱节点对齐。
4. **评测**:自建 100–200 份中文简历标注集(覆盖单栏/双栏、应届/社招、Word/PDF),用 SmartResume 开源的"匈牙利对齐 + 多策略匹配"评测框架跑字段级 F1,技能项另算 set-based F1;每次 prompt/模型变更回归一遍。

二期(若一期在双栏/花哨版式上掉点):

- 引入 SmartResume 的版面检测 + 阅读顺序重建(或 MinerU 转 Markdown)作为预处理,论文数据显示可再提 2–4 个点;
- 若成本/时延成为瓶颈,可参考其行号指针机制减少输出 token,或蒸馏/微调小模型本地部署(Qwen3-0.6B-SFT 路线,F1 0.964 且 1.5s/份)。

预期效果:DeepSeek-v3 代际模型在同类管线中零样本字段级 F1 已达 0.944–0.950,一期"文本直读 + DeepSeek"落在 0.92 上下有论文数据支撑,90% 目标可达;成本约 ¥0.01–0.02/份,时延秒级。

## 六、关键来源

- SmartResume 仓库:https://github.com/alibaba/SmartResume (Apache-2.0)
- SmartResume 论文:Zhu et al., *Layout-Aware Parsing Meets Efficient LLMs*, arXiv:2510.09722 — https://arxiv.org/abs/2510.09722 (数据集、指标定义、全部对比数字的出处)
- Chinese Resume NER:Zhang & Yang, *Chinese NER Using Lattice LSTM*, ACL 2018 — https://github.com/jiesutd/LatticeLSTM
- DeepSeek 官方定价(峰谷计价公告转载):https://www.ithome.com/0/989/418.htm ;官方文档 https://api-docs.deepseek.com
- pdfplumber:https://github.com/jsvine/pdfplumber ;PyMuPDF:https://github.com/pymupdf/PyMuPDF ;python-docx:https://github.com/python-openxml/python-docx
- pyresparser 维护状态:https://deps.dev/project/github/omkarpathak%2fpyresparser
