import { useCallback } from 'react';
import {
  ReactFlow, Background, Controls, type Node, type Edge,
  Position, MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface PipelineDAGProps {
  nodes: Array<{
    id: string;
    type: string; // 'agentStep' | 'approvalGate' | 'toolCall' | 'resource'
    label: string;
    status?: string;
    version?: string; // For resource nodes: current version badge
  }>;
  edges: Array<{
    source: string;
    target: string;
    constraint?: 'passed' | 'trigger'; // Concourse-style edge types
    label?: string;
  }>;
  onNodeClick?: (nodeId: string) => void;
}

const statusColors: Record<string, string> = {
  succeeded: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  pending: '#9ca3af',
  skipped: '#9ca3af',
  waiting_approval: '#eab308',
  approved: '#14b8a6',
  rejected: '#ef4444',
};

const typeColors: Record<string, string> = {
  agentStep: '#3b82f6',
  approvalGate: '#eab308',
  toolCall: '#6b7280',
  resource: '#8b5cf6',
};

export function PipelineDAG({ nodes: inputNodes, edges: inputEdges, onNodeClick }: PipelineDAGProps) {
  const nodes: Node[] = inputNodes.map((n, i) => ({
    id: n.id,
    position: { x: 200 * i, y: 100 },
    data: { label: n.version ? `${n.label}\n${n.version}` : n.label },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    style: {
      background: statusColors[n.status ?? ''] ?? typeColors[n.type] ?? '#e5e7eb',
      color: '#fff',
      border: n.status === 'running' ? '2px solid #facc15' : n.status === 'waiting_approval' ? '2px solid #eab308' : '1px solid #d1d5db',
      borderRadius: n.type === 'approvalGate' ? '50%' : n.type === 'resource' ? '16px' : '8px',
      padding: '10px 16px',
      fontSize: '12px',
      fontWeight: 500,
    },
  }));

  const edges: Edge[] = inputEdges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: inputNodes.find((n) => n.id === e.source)?.status === 'running',
    markerEnd: { type: MarkerType.ArrowClosed },
    style: {
      stroke: e.constraint === 'trigger' ? '#eab308' : '#6b7280',
      strokeDasharray: e.constraint === 'passed' ? '5 5' : undefined,
    },
    labelStyle: { fontSize: 11, fill: '#eab308' },
  }));

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  return (
    <div style={{ height: 400, width: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={handleNodeClick}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
