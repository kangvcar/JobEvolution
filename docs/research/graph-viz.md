# 调研:大规模图可视化与动效库选型

> 工单:[#5 调研:大规模图可视化与动效库选型](https://github.com/kangvcar/JobEvolution/issues/5),Part of #1
> 背景:岗位能力图谱产品(赛题 XH-202621),React + Next.js,暗色大屏基调,图规模千级节点。
> 两大签名交互:① 采集数据流动效(采集事件实时流入图谱);② 演化时间轴回放(拖时间轴看节点/边增删改)。
> 调研日期:2026-08-28,所有结论以官方文档 / 官方仓库 / 官方示例为准。

## 一、结论速览

**主选 AntV G6 v5(配 React 封装 Graphin 3.x),ECharts 作大屏周边图表的补充;react-force-graph 作为 3D 炫技备选。**

- G6 是唯一同时原生覆盖"千级节点 WebGL 渲染 + 时间轴插件 + 自定义持续动效 + 中文文档"四项需求的库,两大签名交互均有官方 API/示例直接背书(详见第三节)。
- ECharts `graph` 系列在千级节点力导向下官方确认会卡,需 echarts-gl 的 `graphGL`,但 graphGL 不支持 timeline 组件联动与自定义边动效,不适合作图谱主体;它的 `lines` 流光特效和 `timeline` 组件适合做大屏周边模块。
- sigma.js 性能最强但动画/时间轴能力最弱;cytoscape.js 偏图分析、WebGL 尚在预览期;react-force-graph 粒子动效最省事但布局仅力导向、无时间轴组件、无中文文档。

## 二、候选库对比

### 2.1 总览表

| 维度 | AntV G6 v5 | ECharts graph / graphGL | sigma.js v3+ | cytoscape.js | react-force-graph |
| --- | --- | --- | --- | --- | --- |
| 渲染技术 | Canvas 默认,可切 SVG / WebGL,支持分层混用 | Canvas(graph);graphGL 为 WebGL | WebGL 为主 | Canvas;3.31+ 提供 WebGL 预览模式 | 2D Canvas / 3D WebGL(three.js) |
| 千级节点 | ✅ WebGL + Rust/WebGPU 布局加速 | graph 力导向千级即卡(官方确认);graphGL 可达万级 | ✅ 设计目标即"数千节点边" | Canvas 千级可用但交互掉帧;WebGL 预览版明显提速 | ✅ 千级流畅,3D 走 GPU |
| 时间轴/回放 | ✅ 官方 Timebar 插件(区间筛选+播放) | timeline 组件(仅 graph,graphGL 不支持) | ❌ 需自行实现 | ❌ 需自行实现 | ❌ 需自行实现 |
| 自定义粒子/流光 | ✅ 自定义元素 + Web Animations(官方蚂蚁线示例) | lines 系列 effect 流光(graph 系列本身无) | ❌ 需自写 WebGL program | 弱(样式动画为主) | ✅ 内置链路粒子 + `emitParticle()` |
| React 集成 | 官方 Graphin 3.x / `@antv/g6-extension-react` React 节点 | echarts-for-react(社区,广泛使用) | 官方 @react-sigma | plotly/react-cytoscapejs(半官方) | 本体即 React 组件 |
| 中文文档 | ✅ 官方中文 | ✅ 官方中文 | ❌ 英文 | ❌ 英文 | ❌ 英文 |

### 2.2 各库要点(附一手来源)

**AntV G6 v5**(12k+ stars,MIT)

- 渲染:默认 Canvas,初始化传 `renderer` 参数即可切 WebGL/SVG,且因分层画布设计支持"主画布 WebGL、其余层 SVG"混用,这也是官方在大图性能 issue 中给出的优化建议。来源:[渲染器文档](https://g6.antv.antgroup.com/manual/further-reading/renderer)、[issue #7402 官方回复](https://github.com/antvis/G6/issues/7402)。
- 布局:v5 布局引擎部分用 Rust 实现(`@antv/layout-wasm`),并提供 `fruchterman-gpu` 等 WebGPU 加速布局。来源:[v5 新特性](https://g6.antv.antgroup.com/en/manual/whats-new/feature)。
- 时间轴:官方 Timebar 插件,支持 `time`(时间轴)/`chart`(趋势图)两种形态、按 `elementTypes`(node/edge/combo)筛选、播放/暂停/前进/后退回调。来源:[Timebar 插件文档](https://g6.antv.antgroup.com/manual/plugin/timebar)。
- 动效:自定义元素 + `onCreate` 生命周期钩子里调 Web Animations API 即可做持续动画,官方文档直接给出"蚂蚁线"(流动边)完整示例(`lineDashOffset` 循环动画,`iterations: Infinity`);节点呼吸灯同理。来源:[动画总览](https://g6.antv.antgroup.com/manual/animation/animation)、[自定义边](https://g6.antv.antgroup.com/en/manual/element/edge/custom-edge)。
- React:官方两条路线,轻集成用 [`在 React 中使用`](https://g6.antv.antgroup.com/manual/getting-started/integration/react) 文档的 hooks 模式(还支持用 `@antv/g6-extension-react` 把 React 组件渲染成图节点);重集成用官方 React 封装 [Graphin 3.x](https://github.com/antvis/graphin)(3.0.5,2025-04 发布,依赖 `@antv/g6 ^5.0.28`,npm 周下载 8 万+)。
- 中文文档:AntV 官方文档中英双语,中文为第一语言。
- 风险:v5 在大图 + 复杂交互下有高 CPU 占用的反馈([issue #7402](https://github.com/antvis/G6/issues/7402)),官方给出的对策是主画布 WebGL、关闭非必要 behaviors、开启 drag/zoom 的 optimize 选项——千级规模按此配置可控。

**Apache ECharts(graph / graphGL)**

- `graph` 系列走 Canvas,力导向在千级节点即明显卡顿,官方维护者在 [issue #5654](https://github.com/apache/echarts/issues/5654) 中确认"这个量级 echarts 里的 graph 确实会卡",并推荐改用 [echarts-gl 的 graphGL](https://echarts.apache.org/zh/option-gl.html#series-graphGL)(布局与渲染均 WebGL 加速,官方 gallery 有万级节点 NPM 依赖图示例)。
- 流光动效:`lines` 系列的 [`effect` 配置](https://echarts.apache.org/zh/option.html#series-lines.effect)(`trailLength` 尾迹、`constantSpeed`、`symbol`)是国内大屏"飞线/迁徙图"的事实标准;注意官方要求带尾迹特效的系列需单独 `zlevel` 并关闭该层 animation。但该特效属于 `lines` 系列,`graph` 系列的边不支持。
- 时间轴:[timeline 组件](https://echarts.apache.org/zh/option.html#timeline) 可在多组 option 间播放切换,适合"逐年快照"式回放;但 echarts-gl 的 graphGL 与 timeline 无联动支持,且快照切换是整图重绘,做不了单个节点/边的增删过渡动画。
- 定位结论:不适合作千级图谱主体,适合做大屏周边(趋势图、事件量迁徙飞线、词云等),与 G6 同属可视化生态、暗色主题风格统一。

**sigma.js v3+**

- 官方定位即"用 WebGL 可视化数千节点与边的图",构建于 graphology 之上,可配 `graphology-layout-forceatlas2` 的 Web Worker 版做非阻塞布局。来源:[官方文档](https://www.sigmajs.org/docs/)、[GitHub](https://github.com/jacomyal/sigma.js)。
- React 集成有官方 [@react-sigma](https://sim51.github.io/react-sigma/),官方 demo 即 React 应用。
- 短板:走自定义 shader 路线,粒子流光、时间轴回放全部要自写 WebGL program 与 UI,无中文文档。性能有富余但工程量最大,对本项目"动效即卖点"的诉求不划算。

**cytoscape.js**

- Canvas 渲染、单线程,官方博客承认大图掉帧:约 1200 节点 + 16000 边时 Canvas 仅约 20 FPS;3.31 起提供 WebGL 渲染预览(`renderer: { name: 'canvas', webgl: true }`),同图可到 100+ FPS,但仍标注为 preview。来源:[官方博客 WebGL Renderer Preview](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/)、[PR #3314](https://github.com/cytoscape/cytoscape.js/pull/3314)。
- 强项在图论算法与分析交互,动效体系(粒子/流光)和时间轴均无内置;React 封装 [plotly/react-cytoscapejs](https://github.com/plotly/react-cytoscapejs) 偏薄。英文文档。不推荐作主体。

**react-force-graph(2D/3D)**

- vasturiano 出品,本体就是 React 组件,2D Canvas / 3D three.js WebGL;千级节点力导向流畅。来源:[官方 README](https://github.com/vasturiano/react-force-graph)。
- 粒子动效开箱即用:`linkDirectionalParticles`(链路上的定向粒子)、`linkDirectionalParticleSpeed/Width/Color`,以及关键的 **`emitParticle(link)` 方法——在指定链路上一次性发射单个粒子**,天然对应"一条采集事件到达就发一颗粒子"的语义;2D 可用 `linkDirectionalParticleCanvasObject` 自绘粒子,3D 可用 `linkDirectionalParticleThreeObject` 自定义材质。来源:[README Props/Methods 表](https://vasturiano.github.io/react-force-graph/)、官方示例 [directional-links-particles](https://vasturiano.github.io/react-force-graph/example/directional-links-particles/)。
- 短板:布局只有 d3-force 力导向(层次/环形等要自己装 dagre 之类换算坐标)、无时间轴组件、样式定制靠自绘回调、英文文档、主要靠作者单人维护。适合作"3D 图谱炫技模式"的备选,不适合承载全部主视图需求。

## 三、两大签名交互可行性

### 3.1 采集数据流动效(事件实时流入图谱)

**G6 方案(主推)**:

1. 流动边:官方动画文档的"蚂蚁线"示例——自定义边继承 `Line`,`onCreate` 中 `this.shapeMap.key.animate([{ lineDashOffset: -20 }, { lineDashOffset: 0 }], { duration, iterations: Infinity })`,即得持续流光效果([动画总览](https://g6.antv.antgroup.com/manual/animation/animation))。
2. 沿边运动的粒子:同一套自定义元素机制,在边的 group 中加 circle 图形,按帧取 path 上的比例点更新位置(G6 v3 时代即有官方 `circle-running` 示例,v5 用 Web Animations 的 `offsetPath`/逐帧回调实现同理,[自定义边文档](https://g6.antv.antgroup.com/en/manual/element/edge/custom-edge) 明确 `onCreate/onUpdate` 钩子用途)。
3. 事件到达时的入场:v5 动画系统内置元素 enter/exit/update 阶段动画,新节点/新边 `graph.addData()` 后自带入场过渡。
4. 底层是 @antv/g 的 Web Animations API,粒子密度、速度、颜色可随采集速率数据驱动。

**react-force-graph 方案(备选,实现成本最低)**:`emitParticle(link)` 一行代码把"一条事件"映射为"一颗粒子",官方 README 明示该方法就是为"非循环、单次发射"设计;搭配 WebSocket/SSE 事件源即成。3D 模式下暗色大屏观感极佳。

**ECharts 方案(周边)**:大屏一侧的"事件流墙/迁徙飞线"用 `lines` + `effect.trailLength` 流光,是最成熟的现成方案,但不作用于图谱本体。

### 3.2 演化时间轴回放(节点/边增删改)

**G6 方案(主推)**:官方 [Timebar 插件](https://g6.antv.antgroup.com/manual/plugin/timebar) 直接覆盖需求:

- 给节点/边数据挂时间戳,`elementTypes: ['node', 'edge']` 即可按时间区间筛选元素;
- `timebarType: 'time'` 是可拖拽时间轴,`'chart'` 是趋势图形态(可用"当期事件量"作 value,契合大屏);
- 内置播放/暂停/单步前进后退,并有 `onChange/onPlay/onPause/onBackward/onForward` 回调;
- 筛选模式可选 modify(改数据)或 visibility(改可见性),配合 v5 元素 enter/exit 动画,节点/边的"增删改"自带过渡效果。

**其余库**:ECharts timeline 只能做整图快照轮播(且 graphGL 不支持);sigma.js / cytoscape.js / react-force-graph 均需自研时间轴 UI + 数据快照 diff。自研 diff 逻辑本身不难(按时间戳过滤 + 增量 add/remove),但时间轴 UI、播放控制、趋势图形态都是纯增量工作量。

## 四、"实时数据流"可视化的开源借鉴

- **粒子流入图谱**:[force-graph 官方 directional-links-particles 示例](https://vasturiano.github.io/react-force-graph/example/directional-links-particles/) 与 `emitParticle` API 是"事件→粒子"最直接的开源参照(即使最终用 G6 实现,交互语义可照搬:事件到达→对应边发射一颗粒子→汇入中心节点时节点脉冲一次)。
- **G6 官方案例库**:[g6.antv.antgroup.com/examples](https://g6.antv.antgroup.com/examples) 中 Animation/Scatter(元素入场退场)、自定义边动画等案例;文档"动画总览"中的蚂蚁线、节点呼吸灯示例可直接改造为采集流动效。
- **事件流墙**:GitHub 公共事件流是最常见的题材,可借鉴 [nat/ghtop](https://github.com/nat/ghtop)(多窗格实时事件流 + 频率 sparkline,信息架构可搬到 Web)与 [leereilly/gh-firehose](https://github.com/leereilly/gh-firehose)(事件消息淡入淡出滚动)。Web 端事件推送通道可参考 [RehanPulse](https://github.com/AIOmarRehan/RehanPulse)(Next.js + SSE 推送 webhook 事件)的做法:采集器落库后经 SSE/WebSocket 推给前端,前端一路驱动事件流墙 DOM 列表(Framer Motion 入场动画即可,无需图形库),一路驱动图谱 `emitParticle`/边流光。
- **大屏飞线**:ECharts 官方"模拟迁徙"示例(`lines` + effect)是国内开源大屏项目(如各类 DataV 仿制大屏)的通用做法,可用于"数据源地域分布→汇聚"的开场页。

## 五、选型推荐

| 层 | 选择 | 理由 |
| --- | --- | --- |
| 图谱主体 | **AntV G6 v5 + Graphin 3.x** | 唯一原生覆盖 Timebar 时间轴 + 自定义持续动效 + WebGL/GPU 布局 + 官方中文文档;两大签名交互均有官方 API 直接背书 |
| 渲染配置 | 主画布 WebGL(`@antv/g-webgl`)、其余层 SVG;力导向用 `fruchterman-gpu` 或 layout-wasm | G6 官方对大图性能问题给出的标准配方 |
| 3D 备选/彩蛋 | react-force-graph(ForceGraph3D) | `emitParticle` 实现"事件→粒子"成本最低,3D 暗色大屏观感强;作为切换视图而非主体 |
| 周边图表 | Apache ECharts | timeline、lines 流光、常规统计图,与 AntV 暗色主题协调,官方中文文档 |
| 明确不选 | sigma.js、cytoscape.js | 前者动效/时间轴全自研不划算;后者 WebGL 仍是 preview、动效体系缺失,且两者均无中文文档 |

主要风险与对策:G6 v5 大图 + 高频交互的 CPU 占用问题(issue #7402)——按官方建议关闭非必要 behaviors、开启 drag-canvas/zoom-canvas 的 optimize、千级规模实测验证后再定稿;Graphin 3.x 社区示例仍以 v2 居多,吃透 G6 v5 原生 API 为主、Graphin 仅作画布容器为宜。

## 六、关键链接汇总

- G6 渲染器(Canvas/SVG/WebGL 分层):https://g6.antv.antgroup.com/manual/further-reading/renderer
- G6 Timebar 插件:https://g6.antv.antgroup.com/manual/plugin/timebar
- G6 动画总览(蚂蚁线/呼吸灯示例):https://g6.antv.antgroup.com/manual/animation/animation
- G6 自定义边(onCreate/onUpdate 钩子):https://g6.antv.antgroup.com/en/manual/element/edge/custom-edge
- G6 v5 新特性(WebGPU/Rust 布局):https://g6.antv.antgroup.com/en/manual/whats-new/feature
- G6 在 React 中使用:https://g6.antv.antgroup.com/manual/getting-started/integration/react
- Graphin 3.x:https://github.com/antvis/graphin
- G6 大图性能 issue:https://github.com/antvis/G6/issues/7402
- ECharts graph 千级卡顿官方确认:https://github.com/apache/echarts/issues/5654
- ECharts graphGL(WebGL 图):https://echarts.apache.org/zh/option-gl.html#series-graphGL
- ECharts lines effect 流光:https://echarts.apache.org/zh/option.html#series-lines.effect
- ECharts timeline:https://echarts.apache.org/zh/option.html#timeline
- sigma.js 文档:https://www.sigmajs.org/docs/
- @react-sigma:https://sim51.github.io/react-sigma/
- cytoscape.js WebGL 预览官方博客:https://blog.js.cytoscape.org/2025/01/13/webgl-preview/
- react-force-graph(linkDirectionalParticles / emitParticle):https://github.com/vasturiano/react-force-graph
- force-graph 粒子官方示例:https://vasturiano.github.io/react-force-graph/example/directional-links-particles/
- ghtop(终端事件流墙):https://github.com/nat/ghtop
- gh-firehose(事件流 + 地球):https://github.com/leereilly/gh-firehose
