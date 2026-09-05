"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Edge,
  Handle,
  MiniMap,
  Node,
  NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  ViewportPortal,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export type FlowSkillData = {
  id: string;
  name: string;
  category?: string | null;
  proficiency?: string;
  levels?: string[];
  sources?: string[];
  kind?: string;
  excerpt?: string;
  confidence?: number;
  layer?: string;
  valid_from?: string | null;
  added?: boolean;
};

export type Neighbor = {
  job_id: string;
  name: string;
  shared_requirements: string[];
  unique_requirements: string[];
};

type SkillNodeData = FlowSkillData & {
  color: string;
  selected: boolean;
  dim: boolean;
  recent: boolean;
  strength: number;
  firstSeen?: string;
  sharedWithNeighbor: boolean;
};

export const SECTOR_ORDER = ["语言", "框架", "平台", "工程", "领域知识", "其他"] as const;
export const SECTOR_COLOR: Record<string, string> = {
  语言: "var(--cat-lang)",
  框架: "var(--cat-frwk)",
  平台: "var(--cat-plat)",
  工程: "var(--cat-engr)",
  领域知识: "var(--cat-know)",
  其他: "var(--cat-other)",
};
const CARD_W = 172;
const CARD_H = 64;
export const RECENT_DAYS = 90;
const MAX_TICKS = 360;
const PROF_LABEL: Record<string, string> = { aware: "了解", able: "熟练", expert: "精通" };
const LAYER_LABEL: Record<string, string> = { high: "高置信", mid: "中置信", low: "低置信" };

const proficiencyLevel = (p?: string) =>
  !p ? 0 : /精通|expert/.test(p) ? 3 : /熟练|able/.test(p) ? 2 : /了解|aware/.test(p) ? 1 : 0;
const proficiencyLabel = (p?: string) => (p ? PROF_LABEL[p] || p : "");

export const sectorOf = (category?: string | null) =>
  (SECTOR_ORDER as readonly string[]).includes(category || "") ? (category as string) : "其他";

const fmtDate = (s?: string | null) => (s ? s.slice(0, 10) : "");

// 所有节点只用一个居中的隐藏 handle，直线边就从卡片中心连到岗位中心，卡片本身盖住重叠段。
function CenterHandle({ type }: { type: "source" | "target" }) {
  return <Handle type={type} position={Position.Top} className="ring-center-handle" isConnectable={false} />;
}

function JobNode({ data }: NodeProps<Node<{ label: string; status?: string; nSources?: number; nWindow?: number; period?: string }>>) {
  const formed = data.status !== "emerging";
  return (
    <div className={`ring-job${formed ? " is-formed" : " is-emerging"}`}>
      <CenterHandle type="source" />
      <div className="ring-job-head">
        <span className="ring-status">{formed ? "成型" : "萌芽"}</span>
        {data.period && <span className="ring-job-period">图谱 {fmtDate(data.period)}</span>}
      </div>
      <div className="ring-job-title">{data.label}</div>
      <div className="ring-job-stats">
        <span>
          <strong>{data.nSources ?? "–"}</strong> 独立源
        </span>
        <span>
          90 天 <strong>{data.nWindow ?? "–"}</strong> 家
        </span>
      </div>
    </div>
  );
}

function SkillNode({ data }: NodeProps<Node<SkillNodeData>>) {
  const bonus = data.kind === "bonus";
  const prof = proficiencyLevel(data.proficiency);
  const sources = data.sources?.length ?? 0;
  const layer = data.layer ? LAYER_LABEL[data.layer] || data.layer : "";
  return (
    <div
      className={`ring-skill${bonus ? " is-bonus" : ""}${data.selected ? " is-selected" : ""}${data.dim ? " is-dim" : ""}${
        data.recent ? " is-recent" : ""
      }${data.sharedWithNeighbor ? " is-shared" : ""}`}
      style={{ "--sector": data.color, width: CARD_W } as React.CSSProperties}
    >
      <CenterHandle type="target" />
      <div className="ring-skill-head">
        <span className="ring-skill-name" title={data.name}>
          {data.name}
        </span>
        {bonus && <span className="ring-tag">加分</span>}
        {!bonus && data.added && <span className="ring-tag new">新</span>}
      </div>
      <div className="ring-skill-meta">
        <span className="ring-meter" title={`熟练级 ${proficiencyLabel(data.proficiency) || "未标"}`}>
          {[1, 2, 3].map((n) => (
            <i key={n} className={n <= prof ? "on" : ""} />
          ))}
          <em>{proficiencyLabel(data.proficiency) || "未标"}</em>
        </span>
        <span className="ring-src" title={layer ? `${sources} 个独立源 · ${layer}` : `${sources} 个独立源`}>
          {sources} 源
        </span>
      </div>
      <div className="ring-skill-bar" aria-hidden="true">
        <i style={{ width: `${Math.round(data.strength * 100)}%` }} />
      </div>
      {(data.excerpt || data.firstSeen) && (
        <div className="ring-excerpt">
          {data.excerpt && <q>{data.excerpt}</q>}
          {data.firstSeen && <span>最早观察 {data.firstSeen}</span>}
        </div>
      )}
    </div>
  );
}

function SectorNode({ data }: NodeProps<Node<{ label: string; count: number; color: string; dim: boolean }>>) {
  return (
    <div className={`ring-sector${data.dim ? " is-dim" : ""}`} style={{ "--sector": data.color } as React.CSSProperties}>
      <i />
      {data.label}
      <b>{data.count}</b>
    </div>
  );
}

function WatchingNode({ data }: NodeProps<Node<{ items: string[] }>>) {
  return (
    <div className="ring-watching">
      <span className="ring-watching-pill">观测中 · {data.items.length}</span>
      <div className="ring-watching-peek">
        {data.items.slice(0, 10).map((name) => (
          <span key={name}>{name}</span>
        ))}
        {data.items.length > 10 && <em>点击查看全部 {data.items.length} 项</em>}
      </div>
    </div>
  );
}

function NeighborNode({ data }: NodeProps<Node<{ neighbor: Neighbor }>>) {
  const n = data.neighbor;
  return (
    <div className="ring-neighbor">
      <CenterHandle type="source" />
      <span className="ring-neighbor-eyebrow">相邻岗位</span>
      <span className="ring-neighbor-name">{n.name}</span>
      <span className="ring-neighbor-meta">
        共享 {n.shared_requirements.length} 项 · 独有 {n.unique_requirements.length} 项
      </span>
    </div>
  );
}

const nodeTypes = { job: JobNode, skill: SkillNode, sector: SectorNode, watching: WatchingNode, neighbor: NeighborNode };

interface FlowCanvasProps {
  job: { id: string; name: string; status?: string };
  stats?: { n_sources?: number; n_window?: number } | null;
  neighbor?: Neighbor | null;
  watching?: string[];
  evidence?: { id: string; observed_at?: string }[];
  period?: string;
  /** 计算"近期"的基准时刻（毫秒），由工作台按 period / 发布时间解析好；period 本身只是展示标签 */
  anchor?: number;
  skills: FlowSkillData[];
  /** 通过工具栏过滤后仍可见的技能 id；null 表示全部可见。被过滤掉的节点变淡而不是消失，位置保持稳定。 */
  visibleIds: Set<string> | null;
  selectedSkill: string;
  onSkillClick: (skill: FlowSkillData) => void;
  onWatchingClick: () => void;
  onNeighborClick: (jobId: string) => void;
}

type Ring = { rx: number; ry: number; items: FlowSkillData[]; label: string };

const ellipsePoint = (rx: number, ry: number, angle: number) => ({ x: rx * Math.cos(angle), y: ry * Math.sin(angle) });

// 找到环上卡片之间最大的角度空隙，环名放在空隙中点就不会压到卡片。
const widestGap = (angles: number[]) => {
  if (!angles.length) return Math.PI * 0.75;
  const sorted = [...angles].sort((a, b) => a - b);
  let best = 0;
  let at = sorted[0] - Math.PI;
  for (let i = 0; i < sorted.length; i++) {
    const next = i + 1 < sorted.length ? sorted[i + 1] : sorted[0] + Math.PI * 2;
    if (next - sorted[i] > best) {
      best = next - sorted[i];
      at = (next + sorted[i]) / 2;
    }
  }
  return at;
};

function InnerFlowCanvas(props: FlowCanvasProps) {
  const { job, stats, neighbor, watching, evidence, period, anchor, skills, visibleIds, selectedSkill, onSkillClick, onWatchingClick, onNeighborClick } = props;
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const [hoverSector, setHoverSector] = useState<string | null>(null);
  const [hoverSkill, setHoverSkill] = useState<string | null>(null);
  const [showMinimap, setShowMinimap] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);

  const dates = useMemo(() => Array.from(new Set(skills.map((s) => fmtDate(s.valid_from)).filter(Boolean))).sort(), [skills]);
  const latest = dates[dates.length - 1];
  // 以图谱发布日为准算"近期"，没有发布日就用今天；不用最晚那条边，否则数据扎堆时全都算近期。
  // period 可能不是日期（"initial"、"2026Q3"），这里只用工作台解析好的 anchor，不再自己 new Date(period)。
  const recentSince = new Date((anchor ?? Date.now()) - RECENT_DAYS * 86400000).toISOString().slice(0, 10);
  const cursorDate = cursor == null ? null : dates[cursor];
  const maxSources = useMemo(() => Math.max(1, ...skills.map((s) => s.sources?.length ?? 0)), [skills]);

  const firstSeen = useMemo(() => {
    const byEvidence = new Map((evidence || []).map((e) => [e.id, fmtDate(e.observed_at)]));
    const out = new Map<string, string>();
    for (const s of skills) {
      const stamps = (s.sources || []).map((id) => byEvidence.get(id)).filter(Boolean) as string[];
      if (stamps.length) out.set(s.id, stamps.sort()[0]);
    }
    return out;
  }, [skills, evidence]);

  useEffect(() => {
    setCursor(null);
    setPlaying(false);
  }, [job.id]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setCursor((c) => {
        const next = (c ?? -1) + 1;
        if (next >= dates.length - 1) setPlaying(false);
        return Math.min(next, dates.length - 1);
      });
    }, 800);
    return () => clearInterval(timer);
  }, [playing, dates.length]);

  const layout = useMemo(() => {
    const sectors = SECTOR_ORDER.map((name) => ({ name, items: skills.filter((s) => sectorOf(s.category) === name) })).filter(
      (s) => s.items.length,
    );
    const total = skills.length || 1;
    const base = Math.max(240, (total * 176) / (2 * Math.PI));
    const required: Ring = { rx: base * 1.32, ry: base * 0.82, items: [], label: "必备要求" };
    const bonus: Ring = { rx: required.rx + 220, ry: required.ry + 130, items: [], label: "加分要求" };
    const hasBonus = skills.some((s) => s.kind === "bonus");
    const outer = hasBonus ? bonus : required;
    const halo = { rx: outer.rx + 100, ry: outer.ry + 70 };
    const labelRing = { rx: required.rx * 0.58, ry: required.ry * 0.58 };

    const placed: { skill: FlowSkillData; x: number; y: number; angle: number; ring: Ring }[] = [];
    const sectorNodes: { name: string; count: number; x: number; y: number }[] = [];
    const dividers: number[] = [];
    let angle = -Math.PI / 2;
    for (const sector of sectors) {
      const span = (2 * Math.PI * sector.items.length) / total;
      dividers.push(angle);
      const mid = angle + span / 2;
      sectorNodes.push({ name: sector.name, count: sector.items.length, ...ellipsePoint(labelRing.rx, labelRing.ry, mid) });
      for (const ring of [required, bonus]) {
        const own = sector.items.filter((s) => (s.kind === "bonus") === (ring === bonus));
        own.forEach((skill, i) => {
          const a = angle + (span * (i + 0.5)) / own.length;
          ring.items.push(skill);
          placed.push({ skill, angle: a, ring, ...ellipsePoint(ring.rx, ring.ry, a) });
        });
      }
      angle += span;
    }
    const rings = [required, ...(hasBonus ? [bonus] : [])].map((ring) => ({
      ...ring,
      labelAngle: widestGap(placed.filter((p) => p.ring === ring).map((p) => p.angle)),
    }));
    return { placed, sectorNodes, dividers: sectors.length > 1 ? dividers : [], rings, halo, required };
  }, [skills]);

  const sharedNames = useMemo(() => new Set(neighbor?.shared_requirements || []), [neighbor]);
  const activeSkill = hoverSkill || selectedSkill;

  const { nodes, edges } = useMemo(() => {
    const visible = (s: FlowSkillData) => {
      if (visibleIds && !visibleIds.has(s.id)) return false;
      const from = fmtDate(s.valid_from);
      if (cursorDate && !(from && from <= cursorDate)) return false;
      return true;
    };
    // initialWidth/initialHeight 让 React Flow 在重新测量前也认为节点有尺寸；否则 stats 与 period 先后到达时
    // 岗位节点会被重置成未测量并卡在 visibility: hidden。
    const nodes: Node[] = [
      {
        id: "job",
        type: "job",
        position: { x: 0, y: 0 },
        initialWidth: 236,
        initialHeight: 110,
        draggable: false,
        data: { label: job.name, status: job.status, nSources: stats?.n_sources, nWindow: stats?.n_window, period },
      },
      ...layout.sectorNodes.map((s) => ({
        id: `sector-${s.name}`,
        type: "sector",
        position: { x: s.x, y: s.y },
        initialWidth: 80,
        initialHeight: 26,
        draggable: false,
        data: { label: s.name, count: s.count, color: SECTOR_COLOR[s.name], dim: Boolean(hoverSector && hoverSector !== s.name) },
      })),
    ];
    const edges: Edge[] = [];
    for (const { skill, x, y } of layout.placed) {
      const sector = sectorOf(skill.category);
      const color = SECTOR_COLOR[sector];
      const from = fmtDate(skill.valid_from);
      const recent = Boolean(from && recentSince && from >= recentSince);
      const dim = !visible(skill) || Boolean(hoverSector && hoverSector !== sector);
      const active = activeSkill === skill.id;
      const sources = skill.sources?.length ?? 0;
      nodes.push({
        id: `skill-${skill.id}`,
        type: "skill",
        initialWidth: CARD_W,
        initialHeight: CARD_H,
        position: { x, y },
        draggable: false,
        className: active ? "is-front" : undefined,
        data: {
          ...skill,
          color,
          selected: active,
          dim,
          recent,
          strength: sources / maxSources,
          firstSeen: firstSeen.get(skill.id),
          sharedWithNeighbor: sharedNames.has(skill.name),
        } satisfies SkillNodeData,
      });
      edges.push({
        id: `e-${skill.id}`,
        source: "job",
        target: `skill-${skill.id}`,
        type: "straight",
        className: `ring-edge${recent ? " is-recent" : ""}${dim ? " is-dim" : ""}${active ? " is-active" : ""}`,
        style: { stroke: color, strokeWidth: Math.min(5, 1 + sources / 3), strokeDasharray: skill.kind === "bonus" ? "6 5" : undefined },
      });
    }
    if (watching?.length) {
      nodes.push({ id: "watching", type: "watching", position: { x: -(layout.halo.rx + 70), y: 0 }, initialWidth: 110, initialHeight: 26, draggable: false, data: { items: watching } });
    }
    if (neighbor) {
      nodes.push({ id: "neighbor", type: "neighbor", position: { x: 0, y: layout.halo.ry + 80 }, initialWidth: 200, initialHeight: 76, draggable: false, data: { neighbor } });
      for (const { skill } of layout.placed) {
        if (!sharedNames.has(skill.name)) continue;
        edges.push({
          id: `n-${skill.id}`,
          source: "neighbor",
          target: `skill-${skill.id}`,
          type: "straight",
          className: "ring-edge is-neighbor",
          style: { strokeWidth: 1.25, strokeDasharray: "2 5" },
        });
      }
    }
    return { nodes, edges };
  }, [layout, job, stats, period, hoverSector, activeSkill, visibleIds, recentSince, cursorDate, firstSeen, watching, neighbor, sharedNames, maxSources]);

  const containerRef = React.useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => fitView({ padding: 0.06, duration: 400 }), 120);
    return () => clearTimeout(timer);
  }, [job.id, layout, fitView]);

  // 面板开合、窗口缩放后重新适配，画布不会留在角落。
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => fitView({ padding: 0.06, duration: 250 }), 120);
    });
    ro.observe(el);
    return () => {
      clearTimeout(timer);
      ro.disconnect();
    };
  }, [fitView]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === "skill") onSkillClick(node.data as unknown as FlowSkillData);
      else if (node.type === "watching") onWatchingClick();
      else if (node.type === "neighbor") onNeighborClick((node.data as { neighbor: Neighbor }).neighbor.job_id);
    },
    [onSkillClick, onWatchingClick, onNeighborClick],
  );
  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.type === "sector") setHoverSector((node.data as { label: string }).label);
    if (node.type === "skill") setHoverSkill((node.data as { id: string }).id);
  }, []);
  const onNodeMouseLeave = useCallback(() => {
    setHoverSector(null);
    setHoverSkill(null);
  }, []);

  const visibleCount = cursorDate ? skills.filter((s) => fmtDate(s.valid_from) <= cursorDate).length : skills.length;

  return (
    <div className="flow-canvas-container ring-canvas" ref={containerRef}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodeOrigin={[0.5, 0.5]}
        onNodeClick={onNodeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={0.15}
        maxZoom={1.8}
        fitView
        fitViewOptions={{ padding: 0.06 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={28} size={1} color="rgba(32,29,29,0.09)" />
        <ViewportPortal>
          <svg className="ring-guides" width={1} height={1} overflow="visible">
            {layout.dividers.map((a) => {
              const p0 = ellipsePoint(layout.required.rx * 0.72, layout.required.ry * 0.72, a);
              const p1 = ellipsePoint(layout.halo.rx, layout.halo.ry, a);
              return <line key={a} x1={p0.x} y1={p0.y} x2={p1.x} y2={p1.y} className="ring-divider" />;
            })}
            {layout.rings.map((ring) => {
              const p = ellipsePoint(ring.rx, ring.ry, ring.labelAngle);
              return (
                <g key={ring.label}>
                  <ellipse rx={ring.rx} ry={ring.ry} className="ring-line" />
                  <text x={p.x} y={p.y} className="ring-label">
                    {ring.label} · {ring.items.length}
                  </text>
                </g>
              );
            })}
            {watching?.length ? (
              <g className="ring-halo">
                {Array.from({ length: Math.min(watching.length, MAX_TICKS) }, (_, i) => {
                  const a = (2 * Math.PI * i) / Math.min(watching.length, MAX_TICKS);
                  const p0 = ellipsePoint(layout.halo.rx - 4, layout.halo.ry - 4, a);
                  const p1 = ellipsePoint(layout.halo.rx + 4, layout.halo.ry + 4, a);
                  return <line key={i} x1={p0.x} y1={p0.y} x2={p1.x} y2={p1.y} />;
                })}
              </g>
            ) : null}
          </svg>
        </ViewportPortal>

        {dates.length > 1 && (
          <div className={`ring-timeline${cursor != null ? " is-on" : ""}`}>
            <button
              type="button"
              className="gw-btn sm"
              onClick={() => {
                if (playing) return setPlaying(false);
                setCursor(cursor == null || cursor >= dates.length - 1 ? 0 : cursor);
                setPlaying(true);
              }}
            >
              {playing ? "暂停" : "回放生效顺序"}
            </button>
            <span className="ring-timeline-date">{dates[0]}</span>
            <input
              type="range"
              min={0}
              max={dates.length - 1}
              value={cursor ?? dates.length - 1}
              aria-label="要求生效时间游标"
              onChange={(e) => {
                setPlaying(false);
                setCursor(Number(e.target.value));
              }}
            />
            <span className="ring-timeline-date">{latest}</span>
            <span className="ring-timeline-readout">
              {cursorDate ? `${cursorDate} · 已生效 ${visibleCount} / ${skills.length}` : `${dates.length} 个生效日`}
            </span>
            {cursor != null && (
              <button
                type="button"
                className="gw-btn sm"
                onClick={() => {
                  setPlaying(false);
                  setCursor(null);
                }}
              >
                退出回放
              </button>
            )}
          </div>
        )}

        <div className="ring-dock" role="toolbar" aria-label="画布工具">
          <button type="button" className="ring-dock-btn" onClick={() => zoomIn({ duration: 200 })} aria-label="放大" title="放大">
            +
          </button>
          <button type="button" className="ring-dock-btn" onClick={() => zoomOut({ duration: 200 })} aria-label="缩小" title="缩小">
            −
          </button>
          <button type="button" className="ring-dock-btn" onClick={() => fitView({ padding: 0.06, duration: 300 })} title="适应窗口">
            全景
          </button>
          <span className="ring-dock-sep" />
          <button
            type="button"
            className={`ring-dock-btn${showMinimap ? " is-active" : ""}`}
            aria-pressed={showMinimap}
            onClick={() => setShowMinimap((v) => !v)}
            title="显示鹰眼"
          >
            鹰眼
          </button>
        </div>

        {showMinimap && (
          <MiniMap
            nodeColor={(node) => (node.type === "job" ? "#201d1d" : node.type === "skill" ? "#9a9898" : "transparent")}
            maskColor="rgba(32,29,29,0.06)"
            className="flow-docked-minimap"
            position="bottom-right"
            style={{ width: 150, height: 100 }}
            pannable
            zoomable
          />
        )}
      </ReactFlow>
    </div>
  );
}

export function FlowWorkbenchCanvas(props: FlowCanvasProps) {
  return (
    <ReactFlowProvider>
      <InnerFlowCanvas {...props} />
    </ReactFlowProvider>
  );
}
