import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
} from '@xyflow/react';
import type { Connection } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AgentStepNode } from '../components/nodes/AgentStepNode';
import { ApprovalGateNode } from '../components/nodes/ApprovalGateNode';

const nodeTypes = {
  agentStep: AgentStepNode,
  approvalGate: ApprovalGateNode,
} as const;

const initialNodes = [
  { id: 'ingest', type: 'agentStep' as const, position: { x: 250, y: 0 }, data: { label: 'Ingest', role: 'pm' } },
  { id: 'route', type: 'agentStep' as const, position: { x: 250, y: 100 }, data: { label: 'Route', role: 'planner' } },
  { id: 'plan', type: 'agentStep' as const, position: { x: 250, y: 200 }, data: { label: 'Plan', role: 'planner' } },
  { id: 'approve_spec', type: 'approvalGate' as const, position: { x: 250, y: 300 }, data: { label: 'Approve Spec' } },
  { id: 'implement', type: 'agentStep' as const, position: { x: 250, y: 400 }, data: { label: 'Implement', role: 'coder' } },
  { id: 'review', type: 'agentStep' as const, position: { x: 250, y: 500 }, data: { label: 'Review', role: 'reviewer' } },
  { id: 'approve_merge', type: 'approvalGate' as const, position: { x: 250, y: 600 }, data: { label: 'Approve Merge' } },
  { id: 'close', type: 'agentStep' as const, position: { x: 250, y: 700 }, data: { label: 'Close', role: 'pm' } },
];

const initialEdges = [
  { id: 'e-ingest-route', source: 'ingest', target: 'route' },
  { id: 'e-route-plan', source: 'route', target: 'plan' },
  { id: 'e-plan-approve', source: 'plan', target: 'approve_spec' },
  { id: 'e-approve-impl', source: 'approve_spec', target: 'implement' },
  { id: 'e-impl-review', source: 'implement', target: 'review' },
  { id: 'e-review-merge', source: 'review', target: 'approve_merge' },
  { id: 'e-merge-close', source: 'approve_merge', target: 'close' },
];

export function Component() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div style={{ height: 'calc(100vh - 120px)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
