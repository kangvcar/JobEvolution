"use client";

import { Graph } from "@antv/g6";

export function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function mountGraph(
  el: HTMLElement,
  data: { nodes: { id: string; data?: Record<string, unknown> }[]; edges: { id: string; source: string; target: string }[] },
  nodeStyle: Record<string, unknown>,
  onNodeClick: (id: string) => void,
) {
  const graph = new Graph({
    container: el,
    autoFit: "view",
    padding: 28,
    data,
    node: { type: "rect", style: nodeStyle },
    edge: { style: { stroke: cssVar("--color-rule") } },
    layout: { type: "dagre", rankdir: "LR", nodesep: 10, ranksep: 72 },
    behaviors: ["drag-canvas", "zoom-canvas"],
  });
  graph.render();
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
