import { useMemo } from 'react';
import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';
import { Position } from '@xyflow/react';

interface UseDagLayoutOptions {
  direction?: 'LR' | 'TB';
  nodeWidth?: number;
  nodeHeight?: number;
  rankSep?: number;
  nodeSep?: number;
}

export function useDagLayout(
  rawNodes: Node[],
  rawEdges: Edge[],
  options: UseDagLayoutOptions = {},
) {
  const {
    direction = 'LR',
    nodeWidth = 200,
    nodeHeight = 60,
    rankSep = 80,
    nodeSep = 40,
  } = options;

  return useMemo(() => {
    if (rawNodes.length === 0) return { nodes: [], edges: rawEdges };

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: direction, ranksep: rankSep, nodesep: nodeSep });

    for (const node of rawNodes) {
      g.setNode(node.id, {
        width: node.measured?.width ?? nodeWidth,
        height: node.measured?.height ?? nodeHeight,
      });
    }

    for (const edge of rawEdges) {
      g.setEdge(edge.source, edge.target);
    }

    dagre.layout(g);

    const isHorizontal = direction === 'LR';

    const positionedNodes = rawNodes.map((node) => {
      const pos = g.node(node.id);
      const w = pos?.width ?? nodeWidth;
      const h = pos?.height ?? nodeHeight;
      return {
        ...node,
        position: {
          x: (pos?.x ?? 0) - w / 2,
          y: (pos?.y ?? 0) - h / 2,
        },
        sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
        targetPosition: isHorizontal ? Position.Left : Position.Top,
      };
    });

    return { nodes: positionedNodes, edges: rawEdges };
  }, [rawNodes, rawEdges, direction, nodeWidth, nodeHeight, rankSep, nodeSep]);
}
