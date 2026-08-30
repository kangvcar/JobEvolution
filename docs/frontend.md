# 前端设计篇

智演长什么样、每页怎么排、动效何时响。画面以 [`prototypes/signature-ui.html`](prototypes/signature-ui.html) 为准。tokens 以 [`prototypes/tokens.css`](prototypes/tokens.css) 为准。信息架构以 [`product.md`](product.md) 为准。接口以 [`tech.md`](tech.md) 为准。术语以根目录 [`CONTEXT.md`](../CONTEXT.md) 为准。

新视觉先改原型再改本文。实现时把 `tokens.css` 原样拷进 `apps/web`，颜色和字体只引用变量名，禁止在组件里写裸 oklch / hex。

一期不做暗色大屏、采集流墙、边上发粒子、G6 Timebar 演化回放、诊断页单独换肤。签名两处：岗位切片画布（含切片差分）、诊断四拍（人话）。

## 设计系统

纸面工作台。直角，发丝分割线，IBM Plex。accent 只用来标当前、萌芽、缺口描边、主按钮。数字用 `tabular-nums`。

把 `docs/prototypes/tokens.css` 整文件搬进前端入口。下面只列实现时必须守住的约束，不另造一套。

**色。** 纸 `--color-paper` / `--color-paper-2`，墨 `--color-ink` / `--color-ink-2` / `--color-muted` / `--color-faint`，线 `--color-rule` / `--color-rule-2`。强调 `--color-accent`（hue 38）配 `--color-accent-ink`。状态：`--color-ok`、`--color-danger`。升值用 `--color-rise`（偏红），贬值 / 新增用 `--color-fall`（偏绿），与股市红涨绿跌相反，跟原型一致。图谱节点：岗位墨底纸字，类目纸底淡描边，必备技能点深描边，加分浅描边。萌芽岗位纸底 + accent 2px 描边。焦点环 `--color-focus`，与 accent 同值。

**字。** `--font-body` / `--font-display` 都是 IBM Plex Sans，中文回落到苹方 / 冬青黑体 / Noto Sans SC。等宽 `--font-mono` 为 IBM Plex Mono，只用于元数据、 pill、快捷键、表头、计数。标题 `font-style: normal`、字重 500、`letter-spacing: -0.02em`。正文 16px / 1.5。不要第二套展示字体。

**空与圆。** 间距走 `--space-*`。页面左右 `--page-gutter`。`--radius-input` / `--radius-card` / `--radius-pill` 全是 0。`border-radius: 0` 写在全局，组件不要再圆。

**动。** 只动 `transform` 和 `opacity`。时长：交互 `--dur-micro`（120ms），入场 `--dur-short`（220ms），面板 `--dur-long`（420ms），交错 `--dur-stagger`（100ms）。缓动默认 `--ease-out`。按钮按下 `scale(0.96)`。不要 `transition: all`。

**高。** sticky 顶栏 `--z-sticky`（200），口令 / ⌘K / 证据抽屉 `--z-modal`（400）。

Next.js 用 `next/font` 拉 IBM Plex Sans 400/500/600 与 IBM Plex Mono 400/500。不要再引 Inter、Geist、系统 UI 栈当正文。

## 壳

顶栏三列：左字标「智演」链到 `/`；中导航 总览 · 图谱 · 诊断 · 发现；右 ⌘K 与「管理」。当前页 `aria-current="page"`，底边 inset 2px accent。顶栏 sticky、高 64px、底发丝。

第一个可聚焦元素是「跳到主内容」。稳定空节点 `role="status"` `aria-live="polite"`，诊断四拍、队列结果改这里的文本。

⌘K 打开命令面板：搜页面或岗位。Esc 关。方向键移动 `aria-selected`。点遮罩关闭。管理入口先弹口令门，通过后再进 `/admin`；取消回刚才那页。证据抽屉从右侧滑入，点遮罩或 Esc 关，焦点回到打开它的按钮。

按钮三类：主按钮 accent 底；幽灵发丝框；危险字色 `--color-rise`。图标按钮必须有 `aria-label`。链到内部路由用 `<Link>` / `<a href>`，动作用 `<button>`。

## 页面规格

路由与产品篇同一张表。Next.js App Router。

### `/` 总览

左图右卷。高度 `100dvh - 64px`。左：四领域岗位图（G6，见下）+ 图例（领域 / 成型 / 萌芽）。右 inspector 从上到下：读数（萌芽 / 谱内）、新岗位发现故事、既有岗更新故事。每条故事两个按钮：打开工作台（`/graph?job=`）、对照这份岗（`/diagnose?job=`）。点图上岗位进工作台。

管线、技能热度、演化流水不占第一屏，折进页底 `<details>`「本周期怎么算出来的」，与发现页同一 `GET /feed`。不要把采集 SSE 画成流墙。计数是库里的聚合。

### `/graph` 图谱

三栏：220px 岗位列表、画布、280px 定义。左栏筛选：领域、技能类目、适用级别（初 / 中 / 高，对应要求边 `levels`）。不按了解 / 熟练 / 精通过滤。搜索框滤岗位名。

中栏只画**当前所选岗位**的类目和技能点，dagre 左→右，并标切片差分：本周期新增 / 升值用 `--color-fall` 描边，已失效用 `--color-rise` 描边并挂在「本周期失效」类目下。点类目折叠/展开技能点。点技能点打开右侧详情并可开证据抽屉。点岗位节点不跳走。主按钮「对照简历」带 `job_id` 去 `/diagnose`。画布 hint 写明差分怎么读。

画布 `role="application"`，进页时 focus。键盘：方向键平移 40px，`+`/`=` 放大 1.12，`-` 缩小，Home `fitView`，Esc 取消选中。鼠标拖画布、滚轮缩放保留。

### `/diagnose` 诊断

一页三态，`data-phase="idle|run|done"`。换简历或离开本页则中止本次分析。邻近岗换岗不停，仍停在 done。打开 `/diagnose?session=&job=` 且会话未过期时，跳过 idle，直接 POST 出报告。done 顶栏有「复制对照链接」。

idle：居中，宽 `min(28rem, 100%)`。领域、目标岗位、简历投放区（PDF / docx，`accept=".pdf,.docx"`）、开始分析。投放区可见标题当标签，文件 input `sr-only` 包在 label 里。`.doc` 与扫描件走技术篇的 400。

run：同一表单还在，主按钮 `disabled` 且保持「开始分析」四字，旁加忙碌。四拍 ticker 见签名交互。请求是同步 `POST /diagnose`，四拍是等待动画，不跟服务端分拍。

done：顶一条细栏（岗位名、复制对照链接、再分析一次）。下左右分栏：左简历预览（会话里的 `preview_text`），右对照报告四组，顺序和标题固定：

1. 判断：AI 总结、档位文案、四格（必备覆盖、半档、经验、学历）、目标岗状态、换档条件。匹配分不渲染成大数字。
2. 定位：对照小图谱、类目覆盖（类目只导航、不对账）、邻近岗并排（当前档位 + 同领域另一岗；默认大模型应用 ↔ Agent）。
3. 行动：学习路径（按换档条件排序，与技术篇一致）、对账表。
4. 解释：对齐痕迹、观测中（对外写「市场开始提，还没进要求，不算缺口」）、简历多出来的技能点、已覆盖。半档 0.5、加分 0.3 只写在这里。

解析失败：写原因 + 可重传，不道歉。扫描件空文本走技术篇的 400。

### `/discover` 发现

候选 / 萌芽 / 成型三列看板。成型列只放切片 3 张，完整名单在图谱左栏。点卡出右侧卷宗（簇、独立源、证据、事件）。管线、热度、升值/贬值、演化流水的主场在本页，与总览 `<details>` 同一 `GET /feed`，不要第二份口径。升值 / 贬值的 pt 是本周期覆盖率百分点变化（12%→33% 即 +21）。候选卡写「未入谱」，无「对照简历」「进工作台」，只开卷宗。已判别名不进候选列，注记在被并入岗的卷宗。批准仍在 `/admin`。

### `/admin` 管理

口令门过后默认待审列表。每条：类型、岗位或技能点、摘要、确认 / 驳回 / 打开证据。低置信条「确认发布」可点，旁注「不可直通」；批了记 `approved`，不记 `auto_passed`。顶栏直通开关 `aria-pressed`，文案「直通关闭 / 直通开启」。开着仍列出自动通过流水。读开关 `GET /admin/passthrough`，改开关 `PUT /admin/passthrough`。

## 签名交互

### 1. 岗位切片画布

在 `/graph` 中栏。这是产品被记住的那张图：一张岗，类目，技能点，加上本周期切片差分。不是四领域全景（全景在总览），也不是时间轴。

触发：进入 `/graph`、改筛选、改选中岗位、折叠类目。布局 dagre `rankdir: LR`。选中节点描边 3px accent。节点 `radius: 0` 的 rect。边发丝 + 箭头。颜色从 CSS 变量读成运行时颜色再喂 G6，不要在 JS 里写死 hex。新增 / 升值节点描边 `--color-fall`，标签前加 `+`。失效节点描边 `--color-rise`，挂在「本周期失效」类目。点这些节点仍开证据。

时长：G6 默认入场即可，不要再套一层页面 stagger。切岗销毁旧实例再 `new Graph`，避免两图叠在同一容器。

### 2. 诊断四拍

run 态。机制不变，字幕用人话，四行固定：

1. 在对你的技能
2. 在读这个岗现在要什么
3. 在标缺口和半档
4. 在定档位

轨道 `translateY`，每拍 700ms，当前行 opacity 1，其余 0.28。每拍把该行写进 live region。四拍结束后才把 done 报告画出来。`prefers-reduced-motion: reduce` 时取消位移，四行同时可见，等请求返回后直接 done。

不要把匹配分、粒子、时间轴、0.5、0.3 塞进这一段。

## 图可视化

库：AntV G6 v5。React 里用官方「在 React 中使用」的容器模式。吃 G6 v5 原生 `Graph` API。不要 Graphin、sigma、cytoscape、react-force-graph、ECharts graph 当主体。

三张图共用节点语义，容器不同：

| 图 | 容器 | 数据 | 点击 |
|---|---|---|---|
| 总览 | `#g6home` | 四 `Domain` + 其下岗位 | 岗位 → `/graph?job=` |
| 工作台 | `#g6` | 当前岗 → 类目 → 技能点，加 `period_delta` | 类目折叠；技能点详情 / 证据 |
| 诊断定位 | `#diagG6` 高 260px | 同工作台切片，技能点带 hit | 技能点 → `/graph` 并选中 |

节点 `k`：`d` 领域、`j` 成型岗位、`e` 萌芽岗位、`c` 技能类目、`s` 必备技能点、`n` 加分技能点。诊断里技能点再加 `hit`：`ok` 墨底、`gap`/`half` accent 描边、`open` 淡描边。

默认 Canvas。单岗节点明显卡顿再切 WebGL。关多余 behavior；`drag-canvas` / `zoom-canvas` 打开 optimize。千级全谱不在工作台画。Timebar 插件不准装。

窗口 resize 时 `graph.resize()` 再 `fitView`。路由切走必须 `graph.destroy()`。

## 亮色阅读

全站同一套纸色，没有暗色主题开关，也没有诊断换肤。诊断 done 才是「阅读」：左简历稿纸（`--color-paper-2` 衬底），右报告 `max-width` 随栏走、段落 `max-width: 62ch`、`text-wrap: pretty`。档位用 `--text-xl` 字重 500，不是仪表盘大数字。

`prefers-contrast: more` 时把 `--color-muted` 降到约 `oklch(0.34 0.03 250)`，`--color-rule` 提到约 `oklch(0.72 0.02 248)`。选择高亮用 accent 28% 透明，字色仍是 ink。

## 响应式

以原型断点为准，内容优先，不要为了「先移动后桌面」重排信息架构。

| 宽 | 做什么 |
|---|---|
| >1100 | 图谱三栏 |
| ≤1100 | 图谱改单列，画布高 420px |
| ≤860 | 诊断 done 改上下：简历在上、最高 40vh；四格改两列；邻近岗并排改单列 |
| ≤700 | 总览改单列，图在上、高 420px |
| ≤640 | 发现看板改单列，卷宗在上 |

`html, body { overflow-x: clip }`。320px 宽无横向滚动。导航链接 `white-space: nowrap`，顶栏允许换行，不要把四字导航折成两行字。可点文案单行。栅格图轨道 `minmax(0, 1fr)`。

触控下主按钮、投放区、看板卡命中面积至少 40×40px；不够就用伪元素撑，不要让扩展区重叠。

200% 缩放仍可完成诊断。输入字号不要小于 16px。禁止 `user-scalable=no`。

## 可访问性底线

- 原生控件优先。不要 `div onClick` 当按钮或链接。
- `:focus-visible` 2px solid `--color-focus`，offset 2px。禁止无替代的 `outline: none`。`forced-colors` 下保留系统描边。
- Tab 走自然序。复合控件（命令面板列表、看板）用 roving tabindex，只 `0` / `-1`。
- 模态（口令、⌘K、证据）给背景 `inert`，打开时焦点进面板，关闭回触发器。`overscroll-behavior: contain`。
- 每个 input 有可见 `<label>`。placeholder 不是标签。
- 提交在请求开始后再 disable，spinner 不替换原标签。失败：`aria-invalid` + `aria-describedby` 指向行内原因，焦点落到第一处。
- 状态不只靠颜色：萌芽有「萌芽」pill，缺口有「缺口」字，升值有「+N pt」（覆盖率百分点）。
- 动效包在 `@media (prefers-reduced-motion: no-preference)`。reduce 时取消位移和 scale，四拍见上。
- 装饰图 `alt=""`。画布的可达名称写在 `aria-label`，不要靠一张截图代替。
- 一页一个 `<h1>` 轮廓。主内容一个 `<main>`。

实现时对着原型走一遍键盘：顶栏 → 各页主路径 → 口令 → ⌘K → 证据抽屉 → 画布快捷键。缺一条就补，不要另写一套无障碍组件库。
