import {
  forceSimulation,
  forceManyBody,
  forceCollide,
  forceX,
  forceY,
  forceLink,
  SimulationNodeDatum,
  SimulationLinkDatum,
} from 'd3-force';

export interface LayoutNode extends SimulationNodeDatum {
  id: string;
  targetX: number;
  targetY: number;
  cluster: 'left' | 'center' | 'right';
  isHub?: boolean;
  width?: number;
  height?: number;
}

export interface LayoutEdge extends SimulationLinkDatum<LayoutNode> {
  id: string;
}

export interface LayoutConfig {
  chargeStrength: number;
  collideRadius: number;
  xStrength: number;
  yStrength: number;
  linkDistance: number;
  linkStrength: number;
}

export interface LayoutMessage {
  type: 'compute';
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  config: LayoutConfig;
}

export interface LayoutResult {
  type: 'result';
  nodes: LayoutNode[];
}

// Web Worker message handler
self.onmessage = (e: MessageEvent<LayoutMessage>) => {
  const { nodes, edges, config } = e.data;

  // Create simulation
  const simulation = forceSimulation(nodes)
    .force(
      'charge',
      forceManyBody()
        .strength(config.chargeStrength)
        .distanceMax(400)
    )
    .force(
      'collide',
      forceCollide<LayoutNode>()
        .radius((d) => config.collideRadius + (d.isHub ? 20 : 0))
        .strength(1.0)
    )
    .force(
      'x',
      forceX<LayoutNode>()
        .x((d) => d.targetX)
        .strength(config.xStrength)
    )
    .force(
      'y',
      forceY<LayoutNode>()
        .y((d) => d.targetY || 0)
        .strength(config.yStrength)
    )
    .force(
      'link',
      forceLink<LayoutNode, LayoutEdge>(edges)
        .id((d) => d.id)
        .distance(config.linkDistance)
        .strength(config.linkStrength)
    )
    .stop();

  // Run simulation to stable state (300 ticks)
  for (let i = 0; i < 300; i++) {
    simulation.tick();
  }

  // Send result back to main thread
  const result: LayoutResult = {
    type: 'result',
    nodes: simulation.nodes(),
  };

  self.postMessage(result);
};
