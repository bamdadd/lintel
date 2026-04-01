import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  BackgroundVariant,
  type OnNodeClick,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { NODE_RENDERERS } from '../../node-registry';
import { AnimatedEdge } from './AnimatedEdge';
import { useDagLayout } from './useDagLayout';
import styles from './DagCanvas.module.css';

const edgeTypes = {
  animated: AnimatedEdge,
};

interface DagCanvasProps {
  nodes: Node[];
  edges: Edge[];
  direction?: 'LR' | 'TB';
  onNodeClick?: (nodeId: string) => void;
  className?: string;
  minHeight?: number;
}

export function DagCanvas({
  nodes: rawNodes,
  edges: rawEdges,
  direction = 'LR',
  onNodeClick,
  className,
  minHeight = 300,
}: DagCanvasProps) {
  const { nodes, edges } = useDagLayout(rawNodes, rawEdges, { direction });

  const handleNodeClick: OnNodeClick = useCallback(
    (_, node: Node) => onNodeClick?.(node.id),
    [onNodeClick],
  );

  return (
    <div className={`${styles.canvas} ${className ?? ''}`} style={{ minHeight }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_RENDERERS}
        edgeTypes={edgeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.5 }}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="rgba(255,255,255,0.03)"
        />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
