"use client";

import React, { useMemo, useCallback, useState, useRef } from "react";
import {
  ReactFlow,
  Background,
  MiniMap,
  Handle,
  Position,
  Node,
  Edge,
  MarkerType,
  BackgroundVariant,
  NodeProps,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useForceLayout } from "./force-layout";
import { useNeighborHighlight } from "./use-neighbor-highlight";

export type FlowSkillData = {
  id: string;
  name: string;
  category?: string | null;
  proficiency?: string;
  levels?: string[];
  sources?: string[];
  kind?: string;
  delta?: "added" | "expired" | "";
  selected?: boolean;
  isDimmed?: boolean;
  isHovered?: boolean;
};

// 1. Zone Indicator Header Badges
export function WingZoneNode({ data }: NodeProps<Node<{ label: string; mode: "decay" | "growth" | "core"; desc?: string }>>) {
  return (
    <div className={`wing-zone-badge ${data.mode}`}>
      <span className="wing-dot" />
      <span>{data.label}</span>
    </div>
  );
}

// 2. Precision Anchor Job Node (Center Spine Origin)
export function JobNode({ data }: NodeProps<Node<{ label: string; status?: "formed" | "emerging"; sourceCount?: number }>>) {
  const isFormed = data.status !== "emerging";

  return (
    <div className={`modern-flow-node job-anchor-node ${isFormed ? "is-formed" : "is-emerging"}`} style={{ width: 240 }}>
      {/* Precision Outgoing Handles */}
      <Handle type="source" id="left" position={Position.Left} className="precision-handle" />
      <Handle type="source" id="right" position={Position.Right} className="precision-handle" />
      <Handle type="source" id="bottom" position={Position.Bottom} className="precision-handle" />

      <div className="node-terminal-header">
        <span className="mono-eyebrow">// TARGET ROLE SPECIFICATION</span>
        <span className={`status-radar-pill ${isFormed ? "formed" : "emerging"}`}>
          <span className="radar-ping-dot" />
          {isFormed ? "成型标准" : "萌芽演化"}
        </span>
      </div>
      <div className="job-anchor-title">{data.label}</div>
      <div className="job-anchor-footer">
        <span className="source-verified-badge">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          双独立企业源持续追踪验证
        </span>
      </div>
    </div>
  );
}

// Category color accents mapping
const CATEGORY_THEMES: Record<string, { label: string; code: string; color: string }> = {
  "语言": { label: "语言", code: "LANG", color: "var(--cat-lang, #0a84ff)" },
  "框架": { label: "框架", code: "FRWK", color: "var(--cat-frwk, #5e5ce6)" },
  "平台": { label: "平台", code: "PLAT", color: "var(--cat-plat, #bf5af2)" },
  "工程": { label: "工程", code: "ENGR", color: "var(--cat-engr, #30d158)" },
  "领域知识": { label: "领域", code: "KNOW", color: "var(--cat-know, #ff9f0a)" },
  "core": { label: "必备标准", code: "CORE", color: "var(--color-ink, #1d1d1f)" },
  "expired": { label: "淘汰退潮", code: "EXPD", color: "var(--cat-expd, #ff453a)" },
  "growth": { label: "增量溢价", code: "INNO", color: "var(--color-fall, #30d158)" },
};

// 3. Category Hub Node (Dock Pill Architecture)
export function CategoryNode({
  data,
}: NodeProps<Node<{ id: string; label: string; code?: string; count: number; isExpired?: boolean; isHovered?: boolean; isDimmed?: boolean }>>) {
  const theme = CATEGORY_THEMES[data.id] || CATEGORY_THEMES[data.label] || {
    label: data.label,
    code: data.code || "SPEC",
    color: data.isExpired ? "#ff453a" : "var(--color-ink, #1d1d1f)",
  };

  return (
    <div
      className={`modern-flow-node category-hub-node${data.isExpired ? " is-expired" : ""}${
        data.isHovered ? " is-hovered" : ""
      }${data.isDimmed ? " is-dimmed" : ""}`}
      style={{ "--hub-accent": theme.color } as React.CSSProperties}
    >
      <Handle type="target" id="top-in" position={Position.Top} className="precision-handle in" />
      <Handle type="target" id="right-in" position={Position.Right} className="precision-handle in" />
      <Handle type="target" id="left-in" position={Position.Left} className="precision-handle in" />

      <Handle type="source" id="bottom-out" position={Position.Bottom} className="precision-handle out" />
      <Handle type="source" id="left-out" position={Position.Left} className="precision-handle out" />
      <Handle type="source" id="right-out" position={Position.Right} className="precision-handle out" />

      <div className="category-hub-inner">
        <span className="hub-theme-dot" />
        <span className="hub-code-tag">{data.code || theme.code}</span>
        <span className="hub-label">{data.label}</span>
        <span className="hub-count-pill">{data.count}</span>
      </div>
    </div>
  );
}

// 4. Precision Capability Specification Node
export function SkillNode({ data }: NodeProps<Node<FlowSkillData>>) {
  const isAdded = data.delta === "added";
  const isExpired = data.delta === "expired";
  const isSelected = Boolean(data.selected);
  const isDimmed = Boolean(data.isDimmed);
  const isHovered = Boolean(data.isHovered);

  // Proficiency dots generator
  const profLevel = data.proficiency?.includes("精通") || data.proficiency === "expert"
    ? 3
    : data.proficiency?.includes("熟练") || data.proficiency === "able"
    ? 2
    : 1;

  return (
    <div
      className={`modern-flow-node skill-spec-node${isSelected ? " is-selected" : ""}${
        isAdded ? " is-added" : ""
      }${isExpired ? " is-expired" : ""}${isDimmed ? " is-dimmed" : ""}${isHovered ? " is-hovered" : ""}`}
    >
      <Handle type="target" id="top-in" position={Position.Top} className="precision-handle in" />
      <Handle type="target" id="left-in" position={Position.Left} className="precision-handle in" />
      <Handle type="target" id="right-in" position={Position.Right} className="precision-handle in" />

      <Handle type="source" id="bottom-out" position={Position.Bottom} className="precision-handle out" />

      <div className="skill-card-top-strip">
        <div className="top-left-badges">
          <span className="skill-meta-cat">{data.category || "能力规范"}</span>
          {data.proficiency && (
            <span className="skill-prof-chip" title={`熟练度等级: ${data.proficiency}`}>
              <span className="prof-dots-wrap">
                <span className={`prof-dot ${profLevel >= 1 ? "filled" : ""}`} />
                <span className={`prof-dot ${profLevel >= 2 ? "filled" : ""}`} />
                <span className={`prof-dot ${profLevel >= 3 ? "filled" : ""}`} />
              </span>
              <span>{data.proficiency}</span>
            </span>
          )}
        </div>
        <div className="top-right-tags">
          {isAdded && <span className="delta-pill added">+新要求</span>}
          {isExpired && <span className="delta-pill expired">-已淘汰</span>}
        </div>
      </div>

      <div className="skill-spec-title" title={data.name}>
        {data.name}
      </div>

      <div className="skill-evidence-bar">
        <span className="verification-count">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          {data.sources?.length || 2} 家在招企业凭证
        </span>
        <span className="view-proof-action">查验 ↗</span>
      </div>
    </div>
  );
}

// 5. Bottom Horizon Frontier Watching Shelf Node
export function FrontierWatchingNode({ data }: NodeProps<Node<{ items: string[] }>>) {
  return (
    <div className="frontier-watching-shelf" style={{ width: 760 }}>
      <div className="frontier-header">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a10 10 0 0 1 10 10" />
          <circle cx="12" cy="12" r="3" />
        </svg>
        <span>市场前沿观测带 // 高频涌现中但尚未确立为正式必备标准</span>
      </div>
      <div className="frontier-chips">
        {data.items.map((item, idx) => (
          <span key={idx} className="frontier-chip">
            <span className="frontier-radar-dot" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

const nodeTypes = {
  wingZone: WingZoneNode,
  jobNode: JobNode,
  categoryNode: CategoryNode,
  skillNode: SkillNode,
  frontierWatching: FrontierWatchingNode,
};

export type CanvasFilterMode = "all" | "added" | "expired" | "core";

interface FlowCanvasProps {
  job: { id: string; name: string; status?: "formed" | "emerging" };
  watching?: string[];
  slice: {
    categories?: { id: string; name: string }[];
    requires?: FlowSkillData[];
    period_delta?: { added?: FlowSkillData[]; expired?: FlowSkillData[] };
  } | null;
  selectedSkill: string;
  onSkillClick: (skill: FlowSkillData) => void;
}

const FALLBACK_WATCHING = [
  "Agentic Workflow 自主代理工作流",
  "MCP 协议标准化集成",
  "端侧小模型量化剪枝与部署",
];

function InnerFlowCanvas({ job, watching, slice, selectedSkill, onSkillClick }: FlowCanvasProps) {
  const { fitView, zoomIn, zoomOut, setViewport } = useReactFlow();

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<CanvasFilterMode>("all");
  const [showMinimap, setShowMinimap] = useState(false);
  const [useForceLayoutEnabled, setUseForceLayoutEnabled] = useState(false);
  const hoverTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Compute Dual-Wing Evolution Balanced Layout
  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node[] = [];
    const rawEdges: Edge[] = [];

    const delta = slice?.period_delta || {};
    const addedIds = new Set((delta.added || []).map((s) => s.id));
    const expiredMap = new Map((delta.expired || []).map((s) => [s.id, s]));

    const allSkills = [...(slice?.requires || [])];
    for (const s of expiredMap.values()) {
      if (!allSkills.some((item) => item.id === s.id)) {
        allSkills.push(s);
      }
    }

    // Partition Skills into 3 Temporal Tiers
    // Tier 1 (Left Wing): Expired / Deprecated
    const leftSkills = allSkills.filter((s) => expiredMap.has(s.id));

    // Tier 3 (Right Wing): Period Added or High-Value Breakthrough
    const rightSkills = allSkills.filter(
      (s) =>
        !expiredMap.has(s.id) &&
        (addedIds.has(s.id) || s.kind === "bonus" || s.category === "领域知识" || s.category === "平台")
    );
    const rightIds = new Set(rightSkills.map((s) => s.id));

    // Tier 2 (Center Spine): Established Core Standard
    const centerSkills = allSkills.filter((s) => !expiredMap.has(s.id) && !rightIds.has(s.id));

    const activeTargetId = hoveredNodeId || (selectedSkill ? `skill-${selectedSkill}` : null);

    // 1. Center Spine Origin: Job Anchor Node
    const JOB_W = 240;
    const jobCenterY = -275;
    rawNodes.push({
      id: "job-root",
      type: "jobNode",
      position: { x: -JOB_W / 2, y: jobCenterY },
      data: {
        label: job.name,
        status: job.status,
        sourceCount: 3,
      },
    });

    // 2. Zone Indicator Headers (Placed cleanly above each wing)
    // Left Zone Header
    rawNodes.push({
      id: "zone-header-decay",
      type: "wingZone",
      position: { x: -640, y: -335 },
      data: {
        label: "◀ 历史退潮区 // 淘汰与降权项 (DEPRECATED AXIS)",
        mode: "decay",
      },
      selectable: false,
      draggable: false,
    });

    // Right Zone Header
    rawNodes.push({
      id: "zone-header-growth",
      type: "wingZone",
      position: { x: 450, y: -335 },
      data: {
        label: "增量突破区 // 新增与高薪溢价 (BREAKTHROUGH AXIS) ▶",
        mode: "growth",
      },
      selectable: false,
      draggable: false,
    });

    // ==========================================
    // A. LEFT WING: Deprecated / Expired Stream
    // ==========================================
    const leftHubX = -520;
    const leftHubY = -115;
    const leftNodeId = "cat-expired";
    const isLeftActive = activeTargetId === leftNodeId || leftSkills.some((s) => `skill-${s.id}` === activeTargetId);

    if (filterMode !== "core" && filterMode !== "added" && leftSkills.length > 0) {
      rawNodes.push({
        id: leftNodeId,
        type: "categoryNode",
        position: { x: leftHubX - 76, y: leftHubY - 20 },
        data: {
          id: "expired",
          label: "淘汰退潮",
          code: "EXPD",
          count: leftSkills.length,
          isExpired: true,
          isHovered: isLeftActive,
          isDimmed: Boolean(activeTargetId && !isLeftActive && activeTargetId !== "job-root"),
        },
      });

      // Edge: Job Anchor Left -> Left Hub
      rawEdges.push({
        id: "e-job-left",
        source: "job-root",
        target: leftNodeId,
        sourceHandle: "left",
        targetHandle: "right-in",
        type: "default",
        animated: isLeftActive,
        style: {
          stroke: "var(--color-rise, #ff453a)",
          strokeWidth: isLeftActive ? 2.5 : 1.5,
          strokeDasharray: "4 4",
          opacity: activeTargetId && !isLeftActive && activeTargetId !== "job-root" ? 0.22 : 0.85,
          transition: "all 150ms ease",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 12,
          height: 12,
          color: "var(--color-rise, #ff453a)",
        },
      });

      // Stacking Expired Skills
      const SKILL_W = 230;
      leftSkills.forEach((skill, idx) => {
        const skillNodeId = `skill-${skill.id}`;
        const isSel = skill.id === selectedSkill;
        const isNodeHovered = activeTargetId === skillNodeId;
        const isNodeFocused = isSel || isNodeHovered || isLeftActive;
        const isDimmed = Boolean(activeTargetId && !isNodeFocused && activeTargetId !== "job-root");

        const skillY = -25 + idx * 115;
        rawNodes.push({
          id: skillNodeId,
          type: "skillNode",
          position: { x: leftHubX - SKILL_W / 2, y: skillY },
          data: {
            ...skill,
            delta: "expired",
            selected: isSel,
            isHovered: isNodeHovered,
            isDimmed,
          },
        });

        // Edge: Left Hub -> Expired Skill
        rawEdges.push({
          id: `e-decay-${skill.id}`,
          source: leftNodeId,
          target: skillNodeId,
          sourceHandle: "bottom-out",
          targetHandle: "top-in",
          type: "default",
          animated: isNodeFocused,
          style: {
            stroke: "var(--color-rise, #ff453a)",
            strokeWidth: isNodeFocused ? 2.5 : 1.5,
            strokeDasharray: "4 4",
            opacity: activeTargetId && !isNodeFocused && activeTargetId !== "job-root" ? 0.22 : 0.85,
            transition: "all 150ms ease",
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 12,
            height: 12,
            color: "var(--color-rise, #ff453a)",
          },
        });
      });
    }

    // ==========================================
    // B. CENTER SPINE: Established Core Standard
    // ==========================================
    const centerHubY = -115;
    const centerHubNodeId = "cat-core-hub";
    const isCenterActive =
      activeTargetId === centerHubNodeId || centerSkills.some((s) => `skill-${s.id}` === activeTargetId);

    if (filterMode !== "expired") {
      rawNodes.push({
        id: centerHubNodeId,
        type: "categoryNode",
        position: { x: -76, y: centerHubY - 20 },
        data: {
          id: "core",
          label: "必备标准",
          code: "CORE",
          count: centerSkills.length,
          isExpired: false,
          isHovered: isCenterActive,
          isDimmed: Boolean(activeTargetId && !isCenterActive && activeTargetId !== "job-root"),
        },
      });

      // Edge: Job Anchor Bottom -> Core Hub
      rawEdges.push({
        id: "e-job-core",
        source: "job-root",
        target: centerHubNodeId,
        sourceHandle: "bottom",
        targetHandle: "top-in",
        type: "default",
        animated: isCenterActive,
        style: {
          stroke: isCenterActive ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #b5b5ba)",
          strokeWidth: isCenterActive ? 2.5 : 1.5,
          opacity: activeTargetId && !isCenterActive && activeTargetId !== "job-root" ? 0.22 : 0.9,
          transition: "all 150ms ease",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 12,
          height: 12,
          color: isCenterActive ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #b5b5ba)",
        },
      });

      // 2 Balanced Sub-Columns under Core Hub: Col 1 at X: -135, Col 2 at X: +135
      const SKILL_W = 230;
      centerSkills.forEach((skill, sIdx) => {
        const isSel = skill.id === selectedSkill;
        const skillNodeId = `skill-${skill.id}`;
        const isNodeHovered = activeTargetId === skillNodeId;
        const isNodeFocused = isSel || isNodeHovered || isCenterActive;
        const isDimmed = Boolean(activeTargetId && !isNodeFocused && activeTargetId !== "job-root");

        const colIndex = sIdx % 2; // 0 = left col, 1 = right col
        const rowIndex = Math.floor(sIdx / 2);
        const posX = colIndex === 0 ? -135 : 135;
        const posY = -25 + rowIndex * 115;

        rawNodes.push({
          id: skillNodeId,
          type: "skillNode",
          position: { x: posX - SKILL_W / 2, y: posY },
          data: {
            ...skill,
            delta: "",
            selected: isSel,
            isHovered: isNodeHovered,
            isDimmed,
          },
        });

        if (rowIndex === 0) {
          // Edge: Core Hub -> Top Row Core Skill
          rawEdges.push({
            id: `e-core-top-${skill.id}`,
            source: centerHubNodeId,
            target: skillNodeId,
            sourceHandle: "bottom-out",
            targetHandle: "top-in",
            type: "default",
            animated: isNodeFocused,
            style: {
              stroke: isNodeFocused ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #ccc)",
              strokeWidth: isNodeFocused ? 2.5 : 1.25,
              opacity: activeTargetId && !isNodeFocused && activeTargetId !== "job-root" ? 0.22 : 0.9,
              transition: "all 150ms ease",
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 12,
              height: 12,
              color: isNodeFocused ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #ccc)",
            },
          });
        } else {
          // Edge: Top Row Skill -> Second Row Skill (Clean vertical hierarchy, NO CROSSING!)
          const parentSkill = centerSkills[sIdx - 2];
          const parentNodeId = parentSkill ? `skill-${parentSkill.id}` : centerHubNodeId;
          rawEdges.push({
            id: `e-core-chain-${skill.id}`,
            source: parentNodeId,
            target: skillNodeId,
            sourceHandle: "bottom-out",
            targetHandle: "top-in",
            type: "default",
            animated: isNodeFocused,
            style: {
              stroke: isNodeFocused ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #ccc)",
              strokeWidth: isNodeFocused ? 2.5 : 1.25,
              strokeDasharray: "3 3",
              opacity: activeTargetId && !isNodeFocused && activeTargetId !== "job-root" ? 0.22 : 0.85,
              transition: "all 150ms ease",
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 12,
              height: 12,
              color: isNodeFocused ? "var(--color-ink, #1d1d1f)" : "var(--color-rule-strong, #ccc)",
            },
          });
        }
      });
    }

    // ==========================================
    // C. RIGHT WING: Period Delta & Breakthrough (2-Column Bento Layout!)
    // ==========================================
    const rightHubX = 570;
    const rightHubY = -115;
    const rightNodeId = "cat-growth";
    const isRightActive = activeTargetId === rightNodeId || rightSkills.some((s) => `skill-${s.id}` === activeTargetId);

    if (filterMode !== "expired") {
      rawNodes.push({
        id: rightNodeId,
        type: "categoryNode",
        position: { x: rightHubX - 76, y: rightHubY - 20 },
        data: {
          id: "growth",
          label: "增量溢价",
          code: "INNO",
          count: rightSkills.length,
          isExpired: false,
          isHovered: isRightActive,
          isDimmed: Boolean(activeTargetId && !isRightActive && activeTargetId !== "job-root"),
        },
      });

      // Edge: Job Anchor Right -> Right Hub
      rawEdges.push({
        id: "e-job-right",
        source: "job-root",
        target: rightNodeId,
        sourceHandle: "right",
        targetHandle: "left-in",
        type: "default",
        animated: true,
        style: {
          stroke: "var(--color-fall, #30d158)",
          strokeWidth: isRightActive ? 2.75 : 1.75,
          opacity: activeTargetId && !isRightActive && activeTargetId !== "job-root" ? 0.22 : 0.9,
          transition: "all 150ms ease",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 12,
          height: 12,
          color: "var(--color-fall, #30d158)",
        },
      });

      // 2 Balanced Sub-Columns in Right Wing:
      // Col 0 at X: 440 (e.g. vLLM, Hybrid Search)
      // Col 1 at X: 700 (e.g. LoRA, CUDA)
      // Generous 75px gap between Center Wing (+250) and Right Wing (+325)!
      const SKILL_W = 230;
      rightSkills.forEach((skill, idx) => {
        const isAdded = addedIds.has(skill.id);
        const isSel = skill.id === selectedSkill;
        const skillNodeId = `skill-${skill.id}`;
        const isNodeHovered = activeTargetId === skillNodeId;
        const isNodeFocused = isSel || isNodeHovered || isRightActive;
        const isDimmed = Boolean(activeTargetId && !isNodeFocused && activeTargetId !== "job-root");

        const colIndex = idx % 2; // 0 = left col, 1 = right col
        const rowIndex = Math.floor(idx / 2);
        const posX = colIndex === 0 ? 440 : 700;
        const posY = -25 + rowIndex * 115;

        rawNodes.push({
          id: skillNodeId,
          type: "skillNode",
          position: { x: posX - SKILL_W / 2, y: posY },
          data: {
            ...skill,
            delta: isAdded ? "added" : "",
            selected: isSel,
            isHovered: isNodeHovered,
            isDimmed,
          },
        });

        if (rowIndex === 0) {
          // Edge: Right Hub -> Top Row Growth Skill
          rawEdges.push({
            id: `e-growth-top-${skill.id}`,
            source: rightNodeId,
            target: skillNodeId,
            sourceHandle: "bottom-out",
            targetHandle: "top-in",
            type: "default",
            animated: isAdded || isNodeFocused,
            style: {
              stroke: isNodeFocused
                ? "var(--color-ink, #1d1d1f)"
                : isAdded
                ? "var(--color-fall, #30d158)"
                : "var(--color-rule-strong, #ccc)",
              strokeWidth: isNodeFocused ? 2.5 : isAdded ? 2 : 1.25,
              opacity: activeTargetId && !isNodeFocused && activeTargetId !== "job-root" ? 0.22 : 0.9,
              transition: "all 150ms ease",
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 12,
              height: 12,
              color: isNodeFocused
                ? "var(--color-ink, #1d1d1f)"
                : isAdded
                ? "var(--color-fall, #30d158)"
                : "var(--color-rule-strong, #ccc)",
            },
          });
        } else {
          // Edge: Top Row Skill -> Second Row Skill (Clean vertical hierarchy, NO CROSSING!)
          const parentSkill = rightSkills[idx - 2];
          const parentNodeId = parentSkill ? `skill-${parentSkill.id}` : rightNodeId;
          rawEdges.push({
            id: `e-growth-chain-${skill.id}`,
            source: parentNodeId,
            target: skillNodeId,
            sourceHandle: "bottom-out",
            targetHandle: "top-in",
            type: "default",
            animated: isAdded || isNodeFocused,
            style: {
              stroke: isNodeFocused
                ? "var(--color-ink, #1d1d1f)"
                : isAdded
                ? "var(--color-fall, #30d158)"
                : "var(--color-rule-strong, #ccc)",
              strokeWidth: isNodeFocused ? 2.5 : isAdded ? 2 : 1.25,
              strokeDasharray: "3 3",
              opacity: activeTargetId && !isNodeFocused && activeTargetId !== "job-root" ? 0.22 : 0.85,
              transition: "all 150ms ease",
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: 12,
              height: 12,
              color: isNodeFocused
                ? "var(--color-ink, #1d1d1f)"
                : isAdded
                ? "var(--color-fall, #30d158)"
                : "var(--color-rule-strong, #ccc)",
            },
          });
        }
      });
    }

    // ==========================================
    // D. BOTTOM SHELF: Market Frontier Radar (Centered at X = 0, Y = 245)
    // ==========================================
    rawNodes.push({
      id: "frontier-watching-shelf",
      type: "frontierWatching",
      position: { x: -380, y: 245 },
      data: {
        items: watching ?? FALLBACK_WATCHING,
      },
      selectable: false,
      draggable: false,
    });

    return { nodes: rawNodes, edges: rawEdges };
  }, [job, slice, selectedSkill, hoveredNodeId, filterMode]);

  // Apply force-directed layout
  const layoutedNodes = useForceLayout(nodes, edges, {
    enabled: useForceLayoutEnabled,
    chargeStrength: -800,
    collideRadius: 140,
    xStrength: 0.15,
    yStrength: 0.05,
    linkDistance: 160,
    linkStrength: 0.3,
  });

  const finalNodes = useForceLayoutEnabled ? layoutedNodes : nodes;

  // Neighbor highlight system
  const { focusedNodeId, neighbors, setFocus, clearFocus } = useNeighborHighlight(finalNodes, edges);

  // Apply neighbor highlighting to nodes
  const highlightedNodes = useMemo(() => {
    if (!focusedNodeId) return finalNodes;

    return finalNodes.map((node) => ({
      ...node,
      className: neighbors.has(node.id)
        ? `${node.className || ""} neighbor-highlighted`.trim()
        : `${node.className || ""} neighbor-dimmed`.trim(),
    }));
  }, [finalNodes, focusedNodeId, neighbors]);

  // Apply neighbor highlighting to edges
  const highlightedEdges = useMemo(() => {
    if (!focusedNodeId) return edges;

    return edges.map((edge) => {
      const sourceId = typeof edge.source === "string" ? edge.source : edge.source;
      const targetId = typeof edge.target === "string" ? edge.target : edge.target;
      const isHighlighted = neighbors.has(sourceId) && neighbors.has(targetId);

      return {
        ...edge,
        className: isHighlighted
          ? `${edge.className || ""} neighbor-highlighted`.trim()
          : `${edge.className || ""} neighbor-dimmed`.trim(),
      };
    });
  }, [edges, focusedNodeId, neighbors]);

  // Smooth Auto Fit View on real content nodes
  React.useEffect(() => {
    if (highlightedNodes.length > 0) {
      const timer = setTimeout(() => {
        fitView({
          nodes: highlightedNodes,
          padding: 0.14,
          duration: 400,
        });
      }, 80);
      return () => clearTimeout(timer);
    }
  }, [highlightedNodes, job.id, filterMode, fitView]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      // Toggle neighbor highlight
      if (focusedNodeId === node.id) {
        clearFocus();
      } else {
        setFocus(node.id);
      }

      // Skill selection
      if (node.type === "skillNode") {
        onSkillClick(node.data as unknown as FlowSkillData);
      }
    },
    [onSkillClick, focusedNodeId, setFocus, clearFocus]
  );

  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.type === "wingZone" || node.type === "frontierWatching") return;
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    setHoveredNodeId((prev) => (prev === node.id ? prev : node.id));
  }, []);

  const onNodeMouseLeave = useCallback((_: React.MouseEvent, node: Node) => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
    }
    hoverTimerRef.current = setTimeout(() => {
      setHoveredNodeId((prev) => (prev === node.id ? null : prev));
    }, 60);
  }, []);

  const handleCenterCore = useCallback(() => {
    fitView({
      nodes: finalNodes,
      padding: 0.14,
      duration: 350,
    });
  }, [fitView, finalNodes]);

  return (
    <div className="flow-canvas-container">
      <ReactFlow
        nodes={highlightedNodes}
        edges={highlightedEdges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        minZoom={0.2}
        maxZoom={1.6}
        defaultEdgeOptions={{ type: "default" }}
      >
        <Background variant={BackgroundVariant.Dots} gap={32} size={1.2} color="rgba(0,0,0,0.08)" />

        {/* Timeline Axis Visualization Layer */}
        <svg className="timeline-axis-overlay" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0 }}>
          <defs>
            {/* Timeline gradient */}
            <linearGradient id="timeline-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(255,69,58,0.1)" />
              <stop offset="35%" stopColor="rgba(255,69,58,0.02)" />
              <stop offset="50%" stopColor="rgba(0,0,0,0.01)" />
              <stop offset="65%" stopColor="rgba(48,209,88,0.02)" />
              <stop offset="100%" stopColor="rgba(48,209,88,0.1)" />
            </linearGradient>

            {/* Edge gradients for visual flow direction */}
            <linearGradient id="edge-gradient-growth" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(48, 209, 88, 0.9)" />
              <stop offset="100%" stopColor="rgba(10, 132, 255, 0.5)" />
            </linearGradient>

            <linearGradient id="edge-gradient-decay" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(255, 69, 58, 0.9)" />
              <stop offset="100%" stopColor="rgba(255, 69, 58, 0.4)" />
            </linearGradient>

            <linearGradient id="edge-gradient-core" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(29, 29, 31, 0.8)" />
              <stop offset="100%" stopColor="rgba(142, 142, 147, 0.5)" />
            </linearGradient>

            <linearGradient id="edge-gradient-focused" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(10, 132, 255, 1)" />
              <stop offset="100%" stopColor="rgba(10, 132, 255, 0.6)" />
            </linearGradient>
          </defs>

          <rect x="0" y="0" width="100%" height="100%" fill="url(#timeline-gradient)" opacity="0.6" />

          {/* Vertical Division Lines */}
          <line x1="33%" y1="0" x2="33%" y2="100%" stroke="rgba(0,0,0,0.06)" strokeWidth="1" strokeDasharray="4 8" />
          <line x1="67%" y1="0" x2="67%" y2="100%" stroke="rgba(0,0,0,0.06)" strokeWidth="1" strokeDasharray="4 8" />

          {/* Timeline Labels */}
          <text x="16.5%" y="30" textAnchor="middle" fill="var(--color-mute)" fontSize="11" fontWeight="700" opacity="0.7">
            ◀ DEPRECATED
          </text>
          <text x="50%" y="30" textAnchor="middle" fill="var(--color-ink)" fontSize="11" fontWeight="700" opacity="0.8">
            ● CORE STANDARD
          </text>
          <text x="83.5%" y="30" textAnchor="middle" fill="var(--color-mute)" fontSize="11" fontWeight="700" opacity="0.7">
            GROWTH ▶
          </text>
        </svg>

        {/* Studio Floating Command Bar (Dual-Wing Evolution Dock) */}
        <div className="studio-canvas-floating-dock">
          {/* Zoom & Centering Segment */}
          <div className="dock-button-group">
            <button
              type="button"
              className="dock-tool-btn"
              onClick={() => zoomIn({ duration: 250 })}
              title="放大全景"
              aria-label="放大"
            >
              +
            </button>
            <button
              type="button"
              className="dock-tool-btn"
              onClick={() => zoomOut({ duration: 250 })}
              title="缩小全景"
              aria-label="缩小"
            >
              −
            </button>
            <button
              type="button"
              className="dock-tool-btn"
              onClick={handleCenterCore}
              title="全屏自适应全景"
              aria-label="自适应"
            >
              ⤢ 全景
            </button>
            <button
              type="button"
              className="dock-tool-btn"
              onClick={() => {
                setViewport({ x: 260, y: 300, zoom: 0.95 }, { duration: 350 });
              }}
              title="聚焦T0现行中枢"
              aria-label="聚焦中枢"
            >
              🎯 聚焦
            </button>
          </div>

          <div className="dock-separator" />

          {/* Quick Highlighting Filter Chips for 3 Temporal Wings */}
          <div className="dock-filter-pills" role="radiogroup" aria-label="时序演化过滤">
            <button
              type="button"
              className={`dock-filter-chip${filterMode === "all" ? " active" : ""}`}
              onClick={() => setFilterMode("all")}
            >
              全时序
            </button>
            <button
              type="button"
              className={`dock-filter-chip${filterMode === "expired" ? " active" : ""}`}
              onClick={() => setFilterMode("expired")}
            >
              <span className="dot exp" /> ◀ 淘汰
            </button>
            <button
              type="button"
              className={`dock-filter-chip${filterMode === "core" ? " active" : ""}`}
              onClick={() => setFilterMode("core")}
            >
              ● 基石
            </button>
            <button
              type="button"
              className={`dock-filter-chip${filterMode === "added" ? " active" : ""}`}
              onClick={() => setFilterMode("added")}
            >
              <span className="dot add" /> 增量 ▶
            </button>
          </div>

          <div className="dock-separator" />

          {/* Force Layout Toggle */}
          <button
            type="button"
            className={`dock-tool-btn${useForceLayoutEnabled ? " is-active" : ""}`}
            onClick={() => setUseForceLayoutEnabled((v) => !v)}
            title={useForceLayoutEnabled ? "切换到固定布局" : "启用智能布局"}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="2" />
              <circle cx="12" cy="5" r="2" />
              <circle cx="19" cy="12" r="2" />
              <circle cx="5" cy="12" r="2" />
              <circle cx="12" cy="19" r="2" />
              <line x1="12" y1="7" x2="12" y2="10" />
              <line x1="12" y1="14" x2="12" y2="17" />
              <line x1="14" y1="12" x2="17" y2="12" />
              <line x1="7" y1="12" x2="10" y2="12" />
            </svg>
            <span>{useForceLayoutEnabled ? "智能" : "固定"}</span>
          </button>

          {/* Neighbor Highlight Clear */}
          {focusedNodeId && (
            <button
              type="button"
              className="dock-tool-btn is-active"
              onClick={clearFocus}
              title="清除邻居高亮"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
              <span>清除高亮</span>
            </button>
          )}

          <div className="dock-separator" />

          {/* Minimap Button */}
          <button
            type="button"
            className={`dock-minimap-btn${showMinimap ? " is-active" : ""}`}
            onClick={() => setShowMinimap((v) => !v)}
            title={showMinimap ? "关闭鹰眼雷达" : "展开鹰眼雷达"}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
              <line x1="15" y1="3" x2="15" y2="21" />
            </svg>
            <span>鹰眼</span>
          </button>
        </div>

        {/* Optional Minimap */}
        {showMinimap && (
          <MiniMap
            nodeStrokeWidth={1.5}
            nodeColor={(node) => {
              if (node.type === "wingZone") return "transparent";
              if (node.type === "jobNode") return "#1d1d1f";
              if (node.type === "categoryNode") return "#8e8e93";
              if (node.data?.delta === "added") return "#30d158";
              if (node.data?.delta === "expired") return "#ff453a";
              return "#c7c7cc";
            }}
            maskColor="rgba(0, 0, 0, 0.08)"
            maskStrokeColor="rgba(0, 0, 0, 0.3)"
            maskStrokeWidth={1}
            className="flow-docked-minimap"
            position="bottom-right"
            style={{ width: 140, height: 90 }}
            zoomable
            pannable
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
