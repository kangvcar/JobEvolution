import { useEffect, useState, useRef } from 'react';
import { Node, Edge } from '@xyflow/react';
import type { LayoutNode, LayoutEdge, LayoutConfig, LayoutResult } from './layout.worker';

export interface ForceLayoutConfig {
  enabled: boolean;
  chargeStrength?: number;
  collideRadius?: number;
  xStrength?: number;
  yStrength?: number;
  linkDistance?: number;
  linkStrength?: number;
}

const DEFAULT_CONFIG: LayoutConfig = {
  chargeStrength: -800,
  collideRadius: 140,
  xStrength: 0.15,
  yStrength: 0.05,
  linkDistance: 160,
  linkStrength: 0.3,
};

export function useForceLayout(
  nodes: Node[],
  edges: Edge[],
  config: ForceLayoutConfig
): Node[] {
  const [layoutedNodes, setLayoutedNodes] = useState<Node[]>(nodes);
  const workerRef = useRef<Worker | null>(null);
  const computingRef = useRef(false);

  useEffect(() => {
    if (!config.enabled) {
      setLayoutedNodes(nodes);
      return;
    }

    // Initialize worker
    if (!workerRef.current) {
      try {
        workerRef.current = new Worker(
          new URL('./layout.worker.ts', import.meta.url),
          { type: 'module' }
        );

        workerRef.current.onmessage = (e: MessageEvent<LayoutResult>) => {
          const { nodes: computedNodes } = e.data;

          // Update React Flow nodes with computed positions
          setLayoutedNodes((prevNodes) =>
            prevNodes.map((node) => {
              const computed = computedNodes.find((n) => n.id === node.id);
              if (computed && computed.x !== undefined && computed.y !== undefined) {
                return {
                  ...node,
                  position: { x: computed.x, y: computed.y },
                };
              }
              return node;
            })
          );

          computingRef.current = false;
        };

        workerRef.current.onerror = (error) => {
          console.error('[ForceLayout] Worker error:', error);
          computingRef.current = false;
        };
      } catch (err) {
        console.error('[ForceLayout] Failed to initialize worker:', err);
        setLayoutedNodes(nodes);
        return;
      }
    }

    // Skip if already computing
    if (computingRef.current) return;

    // Prepare data for worker
    const layoutNodes: LayoutNode[] = nodes
      .filter((n) => n.type !== 'wingZone' && n.type !== 'frontierWatching')
      .map((node) => {
        // Determine cluster based on node position or data
        let cluster: 'left' | 'center' | 'right' = 'center';
        let targetX = node.position.x;

        if (node.id === 'cat-expired' || node.id.includes('cat-expired')) {
          cluster = 'left';
          targetX = -520;
        } else if (node.id === 'cat-growth' || node.id.includes('cat-growth')) {
          cluster = 'right';
          targetX = 570;
        } else if (node.id === 'cat-core-hub') {
          cluster = 'center';
          targetX = 0;
        } else if (node.position.x < -200) {
          cluster = 'left';
          targetX = -520;
        } else if (node.position.x > 300) {
          cluster = 'right';
          targetX = 570;
        }

        return {
          id: node.id,
          x: node.position.x,
          y: node.position.y,
          targetX,
          targetY: node.position.y,
          cluster,
          isHub: node.type === 'categoryNode' || node.type === 'jobNode',
          width: 240,
          height: 95,
        };
      });

    const layoutEdges: LayoutEdge[] = edges
      .filter((e) => {
        const sourceNode = layoutNodes.find((n) => n.id === e.source);
        const targetNode = layoutNodes.find((n) => n.id === e.target);
        return sourceNode && targetNode;
      })
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
      }));

    if (layoutNodes.length === 0) {
      setLayoutedNodes(nodes);
      return;
    }

    // Send compute message to worker
    computingRef.current = true;
    const layoutConfig: LayoutConfig = {
      ...DEFAULT_CONFIG,
      ...(config.chargeStrength !== undefined && { chargeStrength: config.chargeStrength }),
      ...(config.collideRadius !== undefined && { collideRadius: config.collideRadius }),
      ...(config.xStrength !== undefined && { xStrength: config.xStrength }),
      ...(config.yStrength !== undefined && { yStrength: config.yStrength }),
      ...(config.linkDistance !== undefined && { linkDistance: config.linkDistance }),
      ...(config.linkStrength !== undefined && { linkStrength: config.linkStrength }),
    };

    workerRef.current?.postMessage({
      type: 'compute',
      nodes: layoutNodes,
      edges: layoutEdges,
      config: layoutConfig,
    });

    return () => {
      computingRef.current = false;
    };
  }, [nodes, edges, config]);

  // Cleanup worker on unmount
  useEffect(() => {
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, []);

  return config.enabled ? layoutedNodes : nodes;
}
