import { useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
} from '@xyflow/react';
import type { Connection, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Button,
  Group,
  Paper,
  Stack,
  TextInput,
  Select,
  Title,
  ActionIcon,
  Text,
} from '@mantine/core';
import { IconTrash, IconPlus } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { AgentStepNode } from '../components/nodes/AgentStepNode';
import { ApprovalGateNode } from '../components/nodes/ApprovalGateNode';

const nodeTypes = {
  agentStep: AgentStepNode,
  approvalGate: ApprovalGateNode,
} as const;

const roles = ['pm', 'planner', 'coder', 'reviewer', 'designer', 'summarizer'];

const initialNodes: Node[] = [
  { id: 'ingest', type: 'agentStep', position: { x: 250, y: 0 }, data: { label: 'Ingest', role: 'pm' } },
  { id: 'route', type: 'agentStep', position: { x: 250, y: 100 }, data: { label: 'Route', role: 'planner' } },
  { id: 'plan', type: 'agentStep', position: { x: 250, y: 200 }, data: { label: 'Plan', role: 'planner' } },
  { id: 'approve_spec', type: 'approvalGate', position: { x: 250, y: 300 }, data: { label: 'Approve Spec' } },
  { id: 'implement', type: 'agentStep', position: { x: 250, y: 400 }, data: { label: 'Implement', role: 'coder' } },
  { id: 'review', type: 'agentStep', position: { x: 250, y: 500 }, data: { label: 'Review', role: 'reviewer' } },
  { id: 'approve_merge', type: 'approvalGate', position: { x: 250, y: 600 }, data: { label: 'Approve Merge' } },
  { id: 'close', type: 'agentStep', position: { x: 250, y: 700 }, data: { label: 'Close', role: 'pm' } },
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
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const addNode = (type: 'agentStep' | 'approvalGate') => {
    const id = `node_${Date.now()}`;
    const maxY = nodes.reduce((max, n) => Math.max(max, n.position.y), 0);
    const newNode: Node = {
      id,
      type,
      position: { x: 250, y: maxY + 120 },
      data: type === 'agentStep'
        ? { label: 'New Step', role: 'coder' }
        : { label: 'New Gate' },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  const deleteSelectedNode = () => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
    setSelectedNode(null);
  };

  const updateNodeData = (field: string, value: string) => {
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, [field]: value } }
          : n,
      ),
    );
    setSelectedNode((prev) =>
      prev ? { ...prev, data: { ...prev.data, [field]: value } } : null,
    );
  };

  const handleSave = () => {
    const workflow = {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    };
    // TODO: persist via API when workflow definitions support saving
    console.log('Workflow:', JSON.stringify(workflow, null, 2));
    notifications.show({ title: 'Saved', message: 'Workflow saved (local only)', color: 'green' });
  };

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex' }}>
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
          <Panel position="top-left">
            <Group gap="xs">
              <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => addNode('agentStep')}>
                Agent Step
              </Button>
              <Button size="xs" leftSection={<IconPlus size={14} />} variant="light" onClick={() => addNode('approvalGate')}>
                Approval Gate
              </Button>
              <Button size="xs" variant="filled" color="green" onClick={handleSave}>
                Save
              </Button>
            </Group>
          </Panel>
        </ReactFlow>
      </div>

      {selectedNode && (
        <Paper
          withBorder
          p="md"
          style={{ width: 280, borderLeft: '1px solid var(--mantine-color-default-border)' }}
        >
          <Stack gap="sm">
            <Group justify="space-between">
              <Title order={5}>Edit Node</Title>
              <ActionIcon color="red" variant="subtle" onClick={deleteSelectedNode}>
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
            <Text size="xs" c="dimmed">ID: {selectedNode.id}</Text>
            <Text size="xs" c="dimmed">Type: {selectedNode.type}</Text>
            <TextInput
              label="Label"
              value={String(selectedNode.data.label ?? '')}
              onChange={(e) => updateNodeData('label', e.currentTarget.value)}
            />
            {selectedNode.type === 'agentStep' && (
              <Select
                label="Role"
                data={roles}
                value={String(selectedNode.data.role ?? '')}
                onChange={(v) => v && updateNodeData('role', v)}
              />
            )}
          </Stack>
        </Paper>
      )}
    </div>
  );
}
