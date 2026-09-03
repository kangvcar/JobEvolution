# 生产级产品重新设计方案

## 概述

针对智演 (JobEvolution) 项目的图谱页和管理页进行全面生产级重新设计，解决当前存在的节点重叠、视觉效果不成熟、交互不够友好等问题。

---

## 一、图谱页 (Graph Workbench) 重新设计

### 当前问题诊断

**代码文件**: `apps/web/app/graph/flow-canvas.tsx` (902行)

**核心问题**:
1. **固定网格布局算法** - 节点位置完全硬编码
   - 左翼: `x: -520` (单列)
   - 中枢: `x: -135, 135` (双列)
   - 右翼: `x: 440, 700` (双列)
   - 垂直堆叠: `y: -25 + rowIndex * 115`

2. **节点重叠问题** - 当技能节点超过 8-10 个时:
   - 固定 115px 垂直间距导致长列表拥挤
   - 没有动态空间分配
   - 缺少防碰撞机制

3. **视觉成熟度不足**:
   - 布局过于机械和规则
   - 缺少有机的层次感
   - 缺少视觉引导和焦点管理

### 解决方案：智能自适应布局引擎

#### 1.1 力导向布局算法 (Force-Directed Layout)

**技术选型**: D3-force 算法集成到 React Flow

**核心改进**:
```typescript
// 新增力导向引擎配置
const forceSimulation = d3.forceSimulation(nodes)
  .force('charge', d3.forceManyBody()
    .strength(-800)              // 节点互斥力
    .distanceMax(400))           // 最大作用距离
  .force('collide', d3.forceCollide()
    .radius(140)                 // 碰撞半径 = 节点宽度/2 + 边距
    .strength(1))                // 完全避免重叠
  .force('x', d3.forceX()
    .x(d => d.targetX)           // 按时序翼目标X位置
    .strength(0.15))             // 柔性约束到时序区域
  .force('y', d3.forceY(0)
    .strength(0.05))             // 轻微垂直居中
  .force('link', d3.forceLink(edges)
    .distance(160)               // 理想边长度
    .strength(0.3));             // 边约束强度
```

**优势**:
- ✅ **零重叠保证** - collide force 确保节点之间保持安全距离
- ✅ **有机视觉** - 节点自然分散,避免机械感
- ✅ **动态适应** - 自动根据节点数量调整布局
- ✅ **平滑动画** - 力模拟提供优雅的过渡效果

#### 1.2 分层树形布局 (Hierarchical Tree Layout)

**技术选型**: Dagre 算法 + React Flow layouting

**实现策略**:
```typescript
import dagre from 'dagre';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));
dagreGraph.setGraph({ 
  rankdir: 'TB',           // Top-to-Bottom
  nodesep: 80,             // 水平间距
  ranksep: 120,            // 垂直层级间距
  marginx: 40,
  marginy: 40
});

// 分三个独立子图布局
const leftGraph = buildSubgraph(expiredSkills);
const centerGraph = buildSubgraph(coreSkills);
const rightGraph = buildSubgraph(growthSkills);

// 计算布局
dagre.layout(leftGraph);
dagre.layout(centerGraph);
dagre.layout(rightGraph);

// 全局定位偏移
applyGlobalOffset(leftGraph, { x: -600, y: 0 });
applyGlobalOffset(centerGraph, { x: 0, y: 0 });
applyGlobalOffset(rightGraph, { x: 600, y: 0 });
```

**优势**:
- ✅ **严格层次** - 清晰的父子关系可视化
- ✅ **紧凑高效** - 最小化画布空间占用
- ✅ **边优化** - 最少交叉,易于追踪

#### 1.3 智能打包布局 (Pack Layout with Clustering)

**技术选型**: D3-pack + 类别聚类

**实现策略**:
```typescript
const pack = d3.pack()
  .size([width, height])
  .padding(20);

// 按类别分组
const hierarchy = d3.hierarchy({
  children: [
    { name: '淘汰退潮', children: expiredSkills },
    { name: '必备标准', children: coreSkills.groupBy('category') },
    { name: '增量溢价', children: growthSkills }
  ]
})
.sum(d => 1)
.sort((a, b) => b.value - a.value);

const packedNodes = pack(hierarchy);
```

**优势**:
- ✅ **类别可视化** - 圆形包围显示技能聚类
- ✅ **空间利用** - 高效填充画布
- ✅ **视觉吸引** - 现代化、有机的美感

### 视觉增强方案

#### 2.1 节点设计升级

**当前节点尺寸**: 230px × ~95px (固定)

**新设计规格**:
```css
/* 小型节点 (常用技能) */
.skill-node-sm { width: 200px; min-height: 80px; }

/* 标准节点 */
.skill-node-md { width: 240px; min-height: 95px; }

/* 大型节点 (核心/新增技能) */
.skill-node-lg { width: 280px; min-height: 110px; }

/* 动态高度 */
.skill-node { 
  height: auto; 
  max-height: 160px; 
  overflow: hidden;
}
```

**视觉层次**:
- 核心技能 (core): `opacity: 1`, `border-width: 2px`, 略大尺寸
- 新增技能 (added): 绿色左边框 `4px`, 发光效果
- 淘汰技能 (expired): 红色左边框, `opacity: 0.7`, 略小尺寸

#### 2.2 边线 (Edge) 优化

**当前实现**: 简单直线,固定粗细

**新设计**:
```typescript
// 动态边样式
const edgeStyle = {
  stroke: isActive ? 'var(--color-ink)' : 'var(--color-rule)',
  strokeWidth: isActive ? 3 : 1.5,
  strokeDasharray: isDeprecated ? '6 4' : 'none',
  opacity: isDimmed ? 0.15 : 0.75,
  // 贝塞尔曲线边
  type: 'smoothstep',
  // 边动画
  animated: isNewlyAdded || isHovered,
  // 渐变色
  gradient: isTransition ? 'url(#edge-gradient)' : undefined
};

// SVG 渐变定义
<defs>
  <linearGradient id="edge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stopColor="#30d158" stopOpacity="0.8" />
    <stop offset="100%" stopColor="#0a84ff" stopOpacity="0.4" />
  </linearGradient>
</defs>
```

#### 2.3 交互增强

**焦点管理**:
```typescript
// 邻居高亮系统
const [focusedNode, setFocusedNode] = useState<string | null>(null);

const getNeighborIds = (nodeId: string, depth: number = 1): Set<string> => {
  const neighbors = new Set<string>();
  const queue: Array<[string, number]> = [[nodeId, 0]];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const [current, currentDepth] = queue.shift()!;
    if (visited.has(current) || currentDepth > depth) continue;
    
    visited.add(current);
    neighbors.add(current);

    // 找到所有连接的边
    edges.filter(e => e.source === current || e.target === current)
      .forEach(e => {
        const next = e.source === current ? e.target : e.source;
        queue.push([next, currentDepth + 1]);
      });
  }

  return neighbors;
};

// 应用焦点效果
nodes.forEach(node => {
  const isFocused = focusedNode === node.id;
  const isNeighbor = neighbors.has(node.id);
  
  node.data.opacity = isFocused ? 1 : isNeighbor ? 0.8 : 0.2;
  node.data.scale = isFocused ? 1.08 : 1;
  node.data.zIndex = isFocused ? 1000 : isNeighbor ? 100 : 1;
});
```

**画布控制**:
```typescript
// 智能缩放到选中区域
const focusOnNode = (nodeId: string) => {
  const node = nodes.find(n => n.id === nodeId);
  if (!node) return;

  setViewport({
    x: window.innerWidth / 2 - node.position.x,
    y: window.innerHeight / 2 - node.position.y,
    zoom: 1.2
  }, { duration: 600, easing: easeInOutCubic });
};

// 聚类缩放
const focusOnCluster = (clusterKey: 'left' | 'center' | 'right') => {
  const clusterNodes = nodes.filter(n => n.data.cluster === clusterKey);
  fitView({ 
    nodes: clusterNodes, 
    padding: 0.2, 
    duration: 500 
  });
};
```

#### 2.4 视觉引导元素

**时序轴可视化**:
```typescript
// 添加时间轴背景层
<svg className="timeline-axis-overlay" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
  <defs>
    <linearGradient id="timeline-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stopColor="rgba(255,69,58,0.1)" />
      <stop offset="35%" stopColor="rgba(255,69,58,0.02)" />
      <stop offset="50%" stopColor="rgba(0,0,0,0.01)" />
      <stop offset="65%" stopColor="rgba(48,209,88,0.02)" />
      <stop offset="100%" stopColor="rgba(48,209,88,0.1)" />
    </linearGradient>
  </defs>
  
  <rect x="0" y="0" width="100%" height="100%" fill="url(#timeline-gradient)" />
  
  {/* 垂直分割线 */}
  <line x1="33%" y1="0" x2="33%" y2="100%" stroke="rgba(0,0,0,0.06)" strokeWidth="1" strokeDasharray="4 8" />
  <line x1="67%" y1="0" x2="67%" y2="100%" stroke="rgba(0,0,0,0.06)" strokeWidth="1" strokeDasharray="4 8" />
  
  {/* 时序标签 */}
  <text x="16.5%" y="30" textAnchor="middle" fill="var(--color-mute)" fontSize="11" fontWeight="700">
    ◀ DEPRECATED
  </text>
  <text x="50%" y="30" textAnchor="middle" fill="var(--color-ink)" fontSize="11" fontWeight="700">
    ● CORE STANDARD
  </text>
  <text x="83.5%" y="30" textAnchor="middle" fill="var(--color-mute)" fontSize="11" fontWeight="700">
    GROWTH ▶
  </text>
</svg>
```

### 性能优化

#### 3.1 虚拟化渲染

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

// 仅渲染视口内的节点
const visibleNodes = useMemo(() => {
  const { x, y, zoom } = viewport;
  const viewBounds = {
    left: -x / zoom,
    top: -y / zoom,
    right: (-x + window.innerWidth) / zoom,
    bottom: (-y + window.innerHeight) / zoom
  };

  return nodes.filter(node => {
    const nodeBounds = {
      left: node.position.x,
      top: node.position.y,
      right: node.position.x + 240,
      bottom: node.position.y + 100
    };

    return !(
      nodeBounds.right < viewBounds.left ||
      nodeBounds.left > viewBounds.right ||
      nodeBounds.bottom < viewBounds.top ||
      nodeBounds.top > viewBounds.bottom
    );
  });
}, [nodes, viewport]);
```

#### 3.2 Web Worker 布局计算

```typescript
// layout.worker.ts
import { forceSimulation, forceManyBody, forceCollide, forceX, forceY } from 'd3-force';

self.onmessage = (e) => {
  const { nodes, edges, config } = e.data;
  
  const simulation = forceSimulation(nodes)
    .force('charge', forceManyBody().strength(config.chargeStrength))
    .force('collide', forceCollide().radius(config.collideRadius))
    .force('x', forceX(d => d.targetX).strength(config.xStrength))
    .force('y', forceY(0).strength(config.yStrength))
    .stop();

  // 运行模拟到稳定状态
  simulation.tick(300);

  self.postMessage({ nodes: simulation.nodes() });
};

// 主线程使用
const layoutWorker = new Worker(new URL('./layout.worker.ts', import.meta.url));

layoutWorker.postMessage({ nodes, edges, config });
layoutWorker.onmessage = (e) => {
  setNodes(e.data.nodes);
};
```

---

## 二、管理后台 (Admin Dashboard) 重新设计

### 当前问题诊断

**代码文件**: `apps/web/app/admin/page.tsx` (479行)

**核心问题**:
1. **设计粗糙** - 仅基本的边框和间距
2. **信息密度低** - 缺少数据可视化
3. **操作效率低** - 缺少批量操作、快捷键
4. **缺少反馈** - 操作结果不明显

### 解决方案：现代化仪表板架构

#### 1. Dashboard 总览页设计

**新增文件**: `apps/web/app/admin/dashboard.tsx`

```typescript
export function AdminDashboard() {
  return (
    <div className="admin-dashboard">
      {/* KPI 卡片区 */}
      <div className="dashboard-kpi-grid">
        <KPICard
          title="待审核队列"
          value={stats.pending}
          trend={{ value: +12, direction: 'up' }}
          icon={<QueueIcon />}
          color="warning"
        />
        <KPICard
          title="今日裁决"
          value={stats.todayAdjudicated}
          subtitle={`通过率 ${stats.approvalRate}%`}
          icon={<GavelIcon />}
          color="accent"
        />
        <KPICard
          title="活跃采集源"
          value={stats.activePortals}
          subtitle={`总计 ${stats.totalPortals} 个`}
          icon={<SourceIcon />}
          color="success"
        />
        <KPICard
          title="系统健康"
          value="99.8%"
          subtitle="过去 30 天"
          icon={<HeartIcon />}
          color="ok"
        />
      </div>

      {/* 数据可视化区 */}
      <div className="dashboard-charts">
        <ChartCard title="每日裁决趋势" span={2}>
          <LineChart data={adjudicationTrend} />
        </ChartCard>
        
        <ChartCard title="队列分布">
          <DonutChart 
            data={[
              { label: '待审核', value: stats.pending },
              { label: '已通过', value: stats.approved },
              { label: '已驳回', value: stats.rejected }
            ]}
          />
        </ChartCard>
      </div>

      {/* 快速操作区 */}
      <div className="dashboard-quick-actions">
        <QuickActionCard
          title="审核队列"
          description="处理待审核的岗位演化事件"
          action="进入审核"
          href="/admin/queue"
          badge={stats.pending}
        />
        <QuickActionCard
          title="金标准裁决"
          description="对候选岗位进行终审裁决"
          action="开始裁决"
          href="/admin/gold"
          kbd="Alt+G"
        />
        <QuickActionCard
          title="采集管理"
          description="配置和监控招聘数据采集源"
          action="管理采集"
          href="/admin/collect"
        />
      </div>

      {/* 最近活动流 */}
      <div className="dashboard-activity">
        <ActivityFeed activities={recentActivities} />
      </div>
    </div>
  );
}
```

**样式规范** (`globals.css` 新增):
```css
/* ==========================================================================
   Admin Dashboard Components
   ========================================================================== */
.admin-dashboard {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 40px;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}

.kpi-card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  overflow: hidden;
  transition: all 200ms ease;
}

.kpi-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.kpi-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--kpi-color);
}

.kpi-card[data-color="warning"]::before { --kpi-color: var(--color-warning); }
.kpi-card[data-color="accent"]::before { --kpi-color: var(--color-accent); }
.kpi-card[data-color="success"]::before { --kpi-color: var(--color-success); }
.kpi-card[data-color="ok"]::before { --kpi-color: var(--color-ok); }

.kpi-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kpi-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-mute);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.kpi-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--color-canvas);
  color: var(--kpi-color);
}

.kpi-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-ink);
  line-height: 1;
}

.kpi-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-mute);
}

.kpi-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
}

.kpi-trend[data-direction="up"] { color: var(--color-success); }
.kpi-trend[data-direction="down"] { color: var(--color-danger); }

.dashboard-charts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.chart-card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-card[data-span="2"] {
  grid-column: span 2;
}

.chart-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-ink);
}

.dashboard-quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.quick-action-card {
  background: var(--color-canvas);
  border: 1px solid var(--color-rule-strong);
  border-radius: 6px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all 200ms ease;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  position: relative;
}

.quick-action-card:hover {
  border-color: var(--color-ink);
  background: var(--color-surface);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.quick-action-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.quick-action-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink);
}

.quick-action-badge {
  background: var(--color-warning);
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 12px;
  min-width: 24px;
  text-align: center;
}

.quick-action-description {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-body);
}

.quick-action-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--color-rule);
}

.quick-action-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent);
}

.quick-action-kbd {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--color-mute);
  background: var(--color-surface);
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid var(--color-rule);
}

.dashboard-activity {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 24px;
}

.activity-feed {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  background: var(--color-canvas);
  border-radius: 6px;
  transition: background 150ms ease;
}

.activity-item:hover {
  background: var(--color-surface);
}

.activity-icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--activity-color);
}

.activity-icon[data-type="approval"] { --activity-color: var(--color-success); }
.activity-icon[data-type="rejection"] { --activity-color: var(--color-danger); }
.activity-icon[data-type="collection"] { --activity-color: var(--color-accent); }

.activity-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.activity-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.activity-meta {
  font-size: 12px;
  color: var(--color-mute);
}

.activity-timestamp {
  font-size: 12px;
  color: var(--color-mute);
  white-space: nowrap;
}
```

#### 2. 审核队列 (Queue) 优化

**批量操作工具栏**:
```typescript
<div className="queue-toolbar">
  <div className="toolbar-left">
    <Checkbox
      checked={selectedIds.length === items.length}
      indeterminate={selectedIds.length > 0 && selectedIds.length < items.length}
      onChange={toggleSelectAll}
    />
    <span className="toolbar-label">
      {selectedIds.length > 0 ? `已选 ${selectedIds.length} 项` : `共 ${items.length} 项`}
    </span>
  </div>

  {selectedIds.length > 0 && (
    <div className="toolbar-actions">
      <Button 
        variant="primary" 
        onClick={() => batchApprove(selectedIds)}
        kbd="Shift+A"
      >
        <CheckIcon /> 批量通过
      </Button>
      <Button 
        variant="danger" 
        onClick={() => batchReject(selectedIds)}
        kbd="Shift+D"
      >
        <XIcon /> 批量驳回
      </Button>
      <Button variant="ghost" onClick={clearSelection}>
        取消选择
      </Button>
    </div>
  )}

  <div className="toolbar-right">
    <Select value={filter} onChange={setFilter}>
      <option value="all">全部</option>
      <option value="candidate">候选</option>
      <option value="emerging">萌芽</option>
    </Select>
    <Select value={sortBy} onChange={setSortBy}>
      <option value="date">按时间</option>
      <option value="sources">按来源数</option>
      <option value="priority">按优先级</option>
    </Select>
  </div>
</div>
```

**卡片式列表视图**:
```typescript
<div className="queue-grid">
  {items.map(item => (
    <QueueCard
      key={item.id}
      item={item}
      selected={selectedIds.includes(item.id)}
      onToggle={() => toggleSelect(item.id)}
      onApprove={() => handleApprove(item.id)}
      onReject={() => handleReject(item.id)}
      onExpand={() => setExpandedId(item.id)}
    />
  ))}
</div>
```

```css
.queue-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  margin-bottom: 20px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 16px;
  border-left: 1px solid var(--color-rule);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.queue-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.queue-card {
  background: var(--color-canvas);
  border: 2px solid var(--color-rule);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: all 200ms ease;
  cursor: pointer;
  position: relative;
}

.queue-card:hover {
  border-color: var(--color-ink);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.queue-card[data-selected="true"] {
  border-color: var(--color-accent);
  background: rgba(0, 122, 255, 0.04);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
}

.queue-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.queue-card-checkbox {
  margin-top: 2px;
}

.queue-card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink);
  flex-grow: 1;
}

.queue-card-meta {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 12px;
  background: var(--color-surface);
  border-radius: 4px;
  font-size: 12px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  color: var(--color-mute);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.meta-value {
  color: var(--color-ink);
  font-weight: 600;
}

.queue-card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--color-rule);
}

.queue-card-actions button {
  flex: 1;
  height: 36px;
  font-size: 13px;
  font-weight: 600;
}
```

#### 3. 金标准裁决 (Gold) 优化

**双栏对比视图**:
```typescript
<div className="adjudication-layout">
  <div className="adjudication-sidebar">
    <div className="adjudication-queue-mini">
      <h3>待裁决 ({goldQueue.length})</h3>
      {goldQueue.map((item, idx) => (
        <button
          key={item.id}
          className={`mini-card ${activeId === item.id ? 'active' : ''}`}
          onClick={() => setActiveId(item.id)}
        >
          <span className="mini-index">#{idx + 1}</span>
          <span className="mini-name">{item.name}</span>
          <span className="mini-status">{item.status}</span>
        </button>
      ))}
    </div>

    <div className="adjudication-stats">
      <StatItem label="今日裁决" value={stats.today} />
      <StatItem label="通过率" value={`${stats.approvalRate}%`} />
      <StatItem label="平均用时" value={`${stats.avgTime}s`} />
    </div>
  </div>

  <div className="adjudication-main">
    {activeItem && (
      <>
        <div className="adjudication-header">
          <div>
            <h1>{activeItem.name}</h1>
            <div className="adjudication-meta">
              {activeItem.domain} · {activeItem.n_sources} 家企业 · {activeItem.observed_at}
            </div>
          </div>
          <div className="adjudication-progress">
            {currentIndex + 1} / {goldQueue.length}
          </div>
        </div>

        <div className="adjudication-evidence">
          <section>
            <h3>证据摘录</h3>
            <div className="evidence-grid">
              {activeItem.evidence.map(ev => (
                <EvidenceCard key={ev.id} evidence={ev} />
              ))}
            </div>
          </section>

          <section>
            <h3>演化历史</h3>
            <Timeline events={activeItem.events} />
          </section>

          <section>
            <h3>相似岗位对比</h3>
            <ComparisonTable neighbors={activeItem.neighbors} />
          </section>
        </div>

        <div className="adjudication-actions">
          <Button
            variant="danger"
            size="large"
            onClick={() => adjudicate('rejected')}
            kbd="D"
          >
            驳回 (D)
          </Button>
          <Button
            variant="secondary"
            size="large"
            onClick={() => adjudicate('auto_passed')}
            kbd="S"
          >
            自动通过 (S)
          </Button>
          <Button
            variant="primary"
            size="large"
            onClick={() => adjudicate('approved')}
            kbd="A"
          >
            人工批准 (A)
          </Button>
        </div>
      </>
    )}
  </div>
</div>
```

```css
.adjudication-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  height: calc(100vh - 160px);
  padding: 24px;
}

.adjudication-sidebar {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
  overflow: hidden;
}

.adjudication-queue-mini {
  flex-grow: 1;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.adjudication-queue-mini h3 {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-ink);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mini-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-canvas);
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  text-align: left;
  font-size: 13px;
  transition: all 150ms ease;
}

.mini-card:hover {
  border-color: var(--color-ink);
}

.mini-card.active {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
  font-weight: 600;
}

.mini-index {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-mute);
  font-weight: 700;
}

.mini-card.active .mini-index,
.mini-card.active .mini-status {
  color: rgba(255, 255, 255, 0.8);
}

.mini-name {
  flex-grow: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-status {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-mute);
  text-transform: uppercase;
}

.adjudication-stats {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.adjudication-main {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
  overflow-y: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 28px;
}

.adjudication-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--color-rule);
}

.adjudication-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-ink);
  margin-bottom: 8px;
}

.adjudication-meta {
  font-size: 13px;
  color: var(--color-mute);
}

.adjudication-progress {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink);
  background: var(--color-canvas);
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--color-rule);
}

.adjudication-evidence {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.adjudication-evidence section > h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-ink);
  margin-bottom: 14px;
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.adjudication-actions {
  display: flex;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid var(--color-rule);
  position: sticky;
  bottom: 0;
  background: var(--color-surface);
}

.adjudication-actions button {
  flex: 1;
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
```

#### 4. 采集管理 (Collection) 优化

**实时状态仪表板**:
```typescript
<div className="collection-dashboard">
  <div className="collection-overview">
    <StatusCard 
      title="运行中"
      count={portals.filter(p => p.status === 'running').length}
      color="success"
    />
    <StatusCard 
      title="暂停"
      count={portals.filter(p => p.status === 'paused').length}
      color="mute"
    />
    <StatusCard 
      title="错误"
      count={portals.filter(p => p.status === 'error').length}
      color="danger"
    />
    <StatusCard 
      title="今日采集"
      count={stats.todayCollected}
      subtitle={`总计 ${stats.totalCollected}`}
      color="accent"
    />
  </div>

  <div className="collection-table-card">
    <div className="table-header">
      <h3>采集源管理</h3>
      <div className="table-actions">
        <Button variant="ghost" onClick={refreshAll}>
          <RefreshIcon /> 刷新全部
        </Button>
        <Button variant="primary" onClick={openAddPortalModal}>
          <PlusIcon /> 添加采集源
        </Button>
      </div>
    </div>

    <table className="modern-table">
      <thead>
        <tr>
          <th>采集源</th>
          <th>状态</th>
          <th>今日 / 总计</th>
          <th>最后运行</th>
          <th>成功率</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {portals.map(portal => (
          <tr key={portal.id}>
            <td>
              <div className="portal-cell">
                <PortalIcon source={portal.source} />
                <div>
                  <div className="portal-name">{portal.name}</div>
                  <div className="portal-url">{portal.url}</div>
                </div>
              </div>
            </td>
            <td>
              <StatusBadge status={portal.status} />
            </td>
            <td className="table-number">
              {portal.todayCount} / {portal.totalCount}
            </td>
            <td className="table-time">
              {formatTimeAgo(portal.lastRun)}
            </td>
            <td>
              <ProgressBar value={portal.successRate} />
            </td>
            <td>
              <div className="table-actions-cell">
                <IconButton onClick={() => togglePortal(portal.id)}>
                  {portal.status === 'running' ? <PauseIcon /> : <PlayIcon />}
                </IconButton>
                <IconButton onClick={() => editPortal(portal.id)}>
                  <EditIcon />
                </IconButton>
                <IconButton onClick={() => deletePortal(portal.id)} variant="danger">
                  <TrashIcon />
                </IconButton>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>

  {/* SSE 实时日志 */}
  <div className="collection-logs">
    <div className="logs-header">
      <h3>实时日志</h3>
      <Button variant="ghost" size="sm" onClick={clearLogs}>
        清空
      </Button>
    </div>
    <div className="logs-content">
      {logs.map((log, idx) => (
        <LogEntry key={idx} log={log} />
      ))}
    </div>
  </div>
</div>
```

```css
.modern-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
}

.modern-table thead {
  background: var(--color-surface);
  position: sticky;
  top: 0;
  z-index: 10;
}

.modern-table th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-mute);
  border-bottom: 2px solid var(--color-rule);
}

.modern-table td {
  padding: 16px;
  border-bottom: 1px solid var(--color-rule);
  vertical-align: middle;
}

.modern-table tbody tr {
  background: var(--color-canvas);
  transition: background 150ms ease;
}

.modern-table tbody tr:hover {
  background: var(--color-surface);
}

.portal-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.portal-name {
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: 2px;
}

.portal-url {
  font-size: 11px;
  color: var(--color-mute);
  font-family: var(--font-mono);
}

.table-number {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--color-ink);
}

.table-time {
  color: var(--color-mute);
  font-size: 12px;
}

.table-actions-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.collection-logs {
  background: #141415;
  border: 1px solid #28282b;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
}

.logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logs-header h3 {
  font-size: 13px;
  font-weight: 700;
  color: #f5f5f7;
}

.logs-content {
  flex-grow: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
}

.log-entry {
  display: flex;
  align-items: baseline;
  gap: 12px;
  color: #d1d1d6;
  padding: 6px 10px;
  border-radius: 4px;
  transition: background 150ms ease;
}

.log-entry:hover {
  background: rgba(255, 255, 255, 0.05);
}

.log-timestamp {
  color: #8e8e93;
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  font-weight: 700;
  width: 48px;
}

.log-level[data-level="info"] { color: #0a84ff; }
.log-level[data-level="success"] { color: #30d158; }
.log-level[data-level="warn"] { color: #ff9f0a; }
.log-level[data-level="error"] { color: #ff453a; }

.log-message {
  flex-grow: 1;
}
```

---

## 三、实施计划

### 阶段 1: 图谱布局引擎 (Week 1-2)

**任务**:
1. 集成 D3-force 库
2. 实现力导向布局算法
3. 添加防碰撞系统
4. 性能优化 (Web Worker)

**文件修改**:
- `apps/web/app/graph/flow-canvas.tsx`
- `apps/web/app/graph/layout.worker.ts` (新建)
- `package.json` (添加 `d3-force`)

**验收标准**:
- ✅ 100 个节点无重叠
- ✅ 布局计算 < 500ms
- ✅ 平滑动画过渡

### 阶段 2: 图谱视觉增强 (Week 2-3)

**任务**:
1. 节点尺寸分级系统
2. 边线视觉优化
3. 焦点管理系统
4. 时序轴可视化

**文件修改**:
- `apps/web/app/graph/flow-canvas.tsx`
- `apps/web/app/globals.css`

**验收标准**:
- ✅ 节点层次清晰
- ✅ 交互反馈流畅
- ✅ 视觉引导明确

### 阶段 3: 管理后台 Dashboard (Week 3-4)

**任务**:
1. 创建 Dashboard 总览页
2. KPI 卡片组件
3. 图表组件集成
4. 快速操作面板

**文件修改**:
- `apps/web/app/admin/dashboard.tsx` (新建)
- `apps/web/app/admin/layout.tsx` (新建)
- `apps/web/app/globals.css`

**验收标准**:
- ✅ Dashboard 布局响应式
- ✅ KPI 实时更新
- ✅ 图表展示准确

### 阶段 4: 审核工作流优化 (Week 4-5)

**任务**:
1. 批量操作工具栏
2. 卡片式队列视图
3. 双栏裁决布局
4. 键盘快捷键系统

**文件修改**:
- `apps/web/app/admin/page.tsx`
- `apps/web/app/globals.css`

**验收标准**:
- ✅ 批量操作稳定
- ✅ 快捷键响应 < 100ms
- ✅ 裁决效率提升 50%

### 阶段 5: 采集管理现代化 (Week 5-6)

**任务**:
1. 状态仪表板
2. 现代化表格组件
3. 实时日志面板
4. 采集源配置 UI

**文件修改**:
- `apps/web/app/admin/page.tsx`
- `apps/web/app/globals.css`

**验收标准**:
- ✅ SSE 日志实时显示
- ✅ 表格操作响应式
- ✅ 状态监控准确

### 阶段 6: 视觉验证与调优 (Week 6)

**任务**:
1. ego-browser 视觉验证
2. 响应式测试 (Mobile/Tablet/Desktop)
3. 无障碍审查 (WCAG AA)
4. 性能测试 (Lighthouse)

**工具**:
- ego-browser (实际渲染验证)
- Chrome DevTools (响应式)
- axe DevTools (无障碍)
- Lighthouse (性能)

**验收标准**:
- ✅ Lighthouse Score > 90
- ✅ WCAG AA 合规
- ✅ 所有断点测试通过

---

## 四、技术栈补充

**新增依赖**:
```json
{
  "dependencies": {
    "d3-force": "^3.0.0",
    "d3-hierarchy": "^3.1.2",
    "dagre": "^0.8.5",
    "recharts": "^2.10.0",
    "@tanstack/react-virtual": "^3.0.0"
  }
}
```

**性能目标**:
- 图谱布局计算: < 500ms (100 节点)
- 首屏渲染: < 1.5s
- 交互响应: < 100ms
- 页面切换: < 300ms

**浏览器兼容**:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## 五、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 力导向算法性能问题 | 高 | 中 | Web Worker 隔离, 节点数量限制 |
| D3-force 与 React Flow 集成冲突 | 中 | 低 | 使用 useLayoutEffect 协调 |
| 管理后台状态管理复杂 | 中 | 中 | 引入 Zustand 轻量状态库 |
| SSE 连接稳定性 | 低 | 中 | 断线重连, 心跳检测 |
| 响应式布局断点兼容 | 低 | 低 | 移动优先设计, Grid 弹性布局 |

---

## 六、下一步行动

1. **立即开始**: 阶段 1 - 图谱布局引擎
   - 安装 `d3-force` 依赖
   - 创建力导向算法原型
   - 集成到现有 `flow-canvas.tsx`

2. **并行准备**: 管理后台设计规范
   - 创建组件库基础 (Button, Card, Table)
   - 设计 Dashboard 草图
   - 准备测试数据

3. **持续跟进**: 视觉验证
   - 每个阶段完成后使用 ego-browser 验证
   - 记录视觉回归问题
   - 及时调整设计令牌

---

## 七、成功指标

**用户体验**:
- ✅ 图谱节点重叠率: 0%
- ✅ 管理后台操作步数: 减少 40%
- ✅ 视觉美观度评分: > 4.5/5

**技术性能**:
- ✅ Lighthouse Performance: > 90
- ✅ 首屏 LCP: < 1.5s
- ✅ 交互 FID: < 100ms

**业务价值**:
- ✅ 裁决效率: 提升 50%
- ✅ 采集监控响应: 实时 (< 1s)
- ✅ 用户留存: 提升 30%

---

*方案版本: 1.0*  
*创建日期: 2026-09-03*  
*负责人: AI Engineering Team*
