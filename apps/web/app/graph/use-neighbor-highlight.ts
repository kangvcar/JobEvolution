import { useState, useCallback, useMemo } from "react";
import type { Node, Edge } from "@xyflow/react";

export interface NeighborHighlightState {
  focusedNodeId: string | null;
  neighbors: Set<string>;
  depth: number;
}

/**
 * Hook for managing neighbor highlighting in the graph
 * Implements BFS to find all connected nodes within a given depth
 */
export function useNeighborHighlight(nodes: Node[], edges: Edge[]) {
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [highlightDepth, setHighlightDepth] = useState<number>(1);

  // Build adjacency map for efficient neighbor lookup
  const adjacencyMap = useMemo(() => {
    const map = new Map<string, Set<string>>();

    nodes.forEach((node) => {
      map.set(node.id, new Set<string>());
    });

    edges.forEach((edge) => {
      const sourceId = typeof edge.source === "string" ? edge.source : edge.source;
      const targetId = typeof edge.target === "string" ? edge.target : edge.target;

      if (map.has(sourceId)) {
        map.get(sourceId)!.add(targetId);
      }
      if (map.has(targetId)) {
        map.get(targetId)!.add(sourceId);
      }
    });

    return map;
  }, [nodes, edges]);

  // Compute neighbors using BFS
  const neighbors = useMemo(() => {
    if (!focusedNodeId) return new Set<string>();

    const visited = new Set<string>();
    const queue: Array<{ nodeId: string; depth: number }> = [{ nodeId: focusedNodeId, depth: 0 }];
    const result = new Set<string>();

    result.add(focusedNodeId); // Include the focused node itself

    while (queue.length > 0) {
      const current = queue.shift()!;

      if (current.depth >= highlightDepth) continue;
      if (visited.has(current.nodeId)) continue;

      visited.add(current.nodeId);

      const adjacent = adjacencyMap.get(current.nodeId);
      if (adjacent) {
        adjacent.forEach((neighborId) => {
          result.add(neighborId);
          if (!visited.has(neighborId)) {
            queue.push({ nodeId: neighborId, depth: current.depth + 1 });
          }
        });
      }
    }

    return result;
  }, [focusedNodeId, highlightDepth, adjacencyMap]);

  const setFocus = useCallback((nodeId: string | null) => {
    setFocusedNodeId(nodeId);
  }, []);

  const setDepth = useCallback((depth: number) => {
    setHighlightDepth(Math.max(1, Math.min(3, depth))); // Clamp to 1-3
  }, []);

  const clearFocus = useCallback(() => {
    setFocusedNodeId(null);
  }, []);

  return {
    focusedNodeId,
    neighbors,
    depth: highlightDepth,
    setFocus,
    setDepth,
    clearFocus,
  };
}
