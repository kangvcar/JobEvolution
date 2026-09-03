"use client";

import { Graph } from "@antv/g6";

export function cssVar(name: string) {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function mountGraph(
  el: HTMLElement,
  data: { nodes: { id: string; data?: Record<string, unknown> }[]; edges: { id: string; source: string; target: string }[] },
  nodeStyle: Record<string, unknown>,
  onNodeClick: (id: string) => void,
) {
  if (!el) return;
  const graph = new Graph({
    container: el,
    autoFit: "center",
    padding: [48, 64, 48, 48],
    zoomRange: [0.2, 1.25],
    data,
    node: {
      type: "rect",
      style: nodeStyle,
    },
    edge: {
      style: {
        stroke: cssVar("--color-rule-strong") || "#d1d1d6",
        lineWidth: 1.5,
      },
    },
    layout: {
      type: "dagre",
      rankdir: "LR",
      nodesep: 18,
      ranksep: 96,
      controlPoints: true,
    },
    behaviors: ["drag-canvas", "zoom-canvas"],
  });

  graph.render();
  graph.fitView();

  graph.on("node:click", (ev) => {
    onNodeClick((ev as { target?: { id?: string } }).target?.id || "");
  });

  const onResize = () => {
    graph.resize();
    graph.fitView();
  };

  window.addEventListener("resize", onResize);
  return () => {
    window.removeEventListener("resize", onResize);
    graph.destroy();
  };
}

