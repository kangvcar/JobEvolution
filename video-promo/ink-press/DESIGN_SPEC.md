# 智演 JobEvolution × Ink Press — 模板替换记录

制作模式：**直接使用模板（Ink Press）**。只继承模板的镜头结构、运动语法、节奏与已调参数；
字体、配色、圆角、材质全部按产品设计 tokens（`apps/web/app/tokens.css`）重新蒙皮。
规格：1920×1080 @ 30fps，1295 帧（43.2s），SFX-only（无 BGM）。

## 产品简报（只读检查得出）

- 产品：智演 JobEvolution —— 多源招聘数据驱动的岗位能力图谱。从 JD 快照中发现新岗位
  （候选 → 萌芽 → 成型）、追踪岗位要求边的增减，并为求职者做简历诊断（档位、换档条件、证据）。
- 受众：技术求职者（后端/全栈转 Agent / 大模型应用方向）、评审与潜在用户。
- 必须展示的功能：① 首页发布版本读数（9 个入谱岗位 / 3,586 份去重 JD）；② 市场演化页
  （岗位表 + 搜索/筛选 + 卷宗）；③ 卷宗中的岗位要求（每条要求边 ≥2 独立源）；④ 图谱工作台
  （拓扑、悬停看 JD 原文、必备筛选、表格视图）——**真实操作录屏**；⑤ 简历诊断五步流程
  ——**真实操作录屏**；⑥ 诊断报告；⑦ 品牌收尾。
- 数据口径：页面数据为产品当前发布版本中的公开演示数据（招聘门户公开 JD 的聚合统计）；
  简历使用仓库自带的脱敏示例简历 `docs/resume/柯蝶旋_Agent工程师_简历.pdf`；管理后台口令页不入镜。
- 已知数据风险（沿用仓库记录）：大模型应用工程师在运行态为候选状态；页面里的“本期 −25”等数字来自当前切片。

## 设计 tokens（来自产品）

| token | 值 | 用途 |
|---|---|---|
| 字体 | `"Berkeley Mono", "IBM Plex Mono", PingFang SC` | 字卡/注记/字幕/kicker（模板 serif → 产品等宽 + 系统 CJK） |
| 纸底 / 表面 | `#fdfcfc` / `#f8f7f7` | 全片底色、字卡底 |
| 墨字 / 次级 | `#201d1d` / `#646262` | 标题、字幕 |
| 强调 | `#007aff`（模板琥珀 → 产品蓝） | 重点词、下划线、光束、涟漪、缝、caret |
| 圆角 | 4px（表面 0） | 卡片切片、补丁、描边 |
| 暗面 | `#201d1d` / `#302c2c` | 牌堆特写的深色桌面（替代暖色拉丝金属，冷光 key） |
| 字标 | 「智演」像素字形 SVG（`apps/web/app/logo.tsx` 路径） | 开场 letterpress、收尾字标 |

## 镜头结构（AIFL_SHOTS，src/aifl/Main.tsx）

| # | 帧 | 时长 | 场景 | 内容 | 镜头卡 | 素材 |
|---|---|---|---|---|---|---|
| 1 | 0–220 | 7.3s | live/SceneOpen | 准星→「智演」字标压印→kicker 打字→1s hold → 首页全景 → 聚光锁定“当前发布版本”读数卡 → 侧向推进、弹起悬浮、光束两圈、3D 注记“9 个岗位在谱 / 3,586 份 JD 作证”→ 归位 | brand-ink-open / spotlight-hero-card | home-full.png（2x）、readout-hires.png（4x） |
| 2 | 220–275 | 1.8s | PaperTitleCard | “3,586 份 JD，长成一张 **岗位能力图谱**。” | paper-title-card | — |
| 3 | 275–465 | 6.3s | live/SceneFlyIn | 深色桌面上 12 条岗位行的牌堆特写环绕 → 拉远接市场演化页 → 硬加速发牌入表 → 0.5s 静止 → 上移到搜索框 → 打字 “Agent”（3f/字符）→ 呼吸 → 非目标行错峰淡出、目标行滑到首行 → 双圈涟漪点击 → 推进 | deck-deal-flyin / type-and-filter | discover-empty.png、row1–12.png、layout.discover |
| 4 | 465–565 | 3.3s | live/SceneDetail | Agent 工程师卷宗：7 条岗位要求行从空中降下嵌入，底边蓝缝 | row-embed | discover-full.png（纹理裁片） |
| 5 | 565–620 | 1.8s | PaperTitleCard | “图谱工作台，看清 **要求边** 怎么来。” 副行 DigitRoll 22 条正式要求 | paper-title-card | — |
| 6 | 620–755 | 4.5s | live/SceneClip | **真实操作录屏**：图谱工作台 → 悬停 LLM 节点看 JD 原文 → 点开证据面板（支持该要求的 JD 快照）→ 必备筛选 → 表格视图 | 录屏 + 2.5D settle | clips/graph-ops.mp4 |
| 7 | 755–805 | 1.7s | PaperTitleCard | “上传一份简历，**换档条件** 算给你看。” | paper-title-card | — |
| 8 | 805–985 | 6.0s | live/SceneClip | **真实操作录屏**：上传简历 → 校对解析 → 确认 → 选对照岗 → 开始对照 → 报告落地（等待段已剪去） | 录屏 + 2.5D settle | clips/diagnose-flow.mp4 |
| 9 | 985–1095 | 3.7s | live/SceneReport | 诊断报告逐块“写出来”（caret 前沿）、结论行蓝色荧光、左侧视图轨道擦入、四个视图项逐个落入 | document-typewriter-reveal | report-full.png、layout.report |
| 10 | 1095–1150 | 1.8s | PaperTitleCard | “每一条结论，都 **回溯** 到简历与 JD 原文。” | paper-title-card | — |
| 11 | 1150–1295 | 4.8s | live/SceneOutroLive | 虚焦 → 各页代表元素四方飞入合影 → 「智演 JobEvolution」压印 → 蓝色短划 → tagline“招聘市场在变，你的换档条件也在变。” → 1s hold | outro-group-photo-launch | nav/readout/rows/req rows/steps/chips/search/graph bar |

叠加层：字幕 7 条（底部通栏，30px 等宽 + 纸底衬板）；FlashCut 4 处（table/macro/graph/report 起点 −5）；
SFX 表按镜头起点相对钉帧（`at(shot, rel)`），录屏内的真实点击另由 `FOOTAGE_CLICKS` 钉 click-camera。

## 与模板的差异（有意为之）

- 增加两个真实操作录屏镜头（用户要求“包含产品的页面和操作录制”），录屏用 CDP 截帧 + 伪光标；
  等待 LLM 解析的时间段在录制时切段剪去。
- 模板论文堆叠镜头（list-stack-press）替换为图谱工作台录屏；周报打字机镜头映射到诊断报告。
- 发牌张数 12（页面真实岗位行数），加速公式改为 gap 4f→0.5f 覆盖 12 张；市场演化页只有一屏高，
  取消长距离追逐 scroll，保留拉远 + 0.5s 满板静止。
- 拉远段的 DoF 顶部虚化在本产品页面上会把整帧读软（浅色纸底 + 细字），已关闭；开场推进的 DoF 峰值 9→5。
- 有意保留产品的绿色“− 失效”芯片颜色（产品语义：fall = success 绿）。

## 素材采集

`capture/capture.mjs`（puppeteer，2x 全页 + 元素切片 + layout.json，隐藏 Next.js 开发角标），
`capture/record-graph.mjs` / `capture/record-diagnose.mjs`（1x 录屏，`rec-lib.mjs` 提供光标与 CDP 截帧），
`capture/assemble-dx.mjs`（诊断分段拼接）。录屏浏览器把 API 请求转到本机 8001 的同镜像 API 副本
（LLM_PROVIDER=deepseek，因为默认 tuzi 模型对简历抽取 60s 超时），不改动仓库 .env 与主容器。
