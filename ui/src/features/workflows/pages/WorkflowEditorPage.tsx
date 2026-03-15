import { useCallback, useState, useEffect } from 'react';
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
  Loader,
  Center,
} from '@mantine/core';
import { IconTrash, IconPlus } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useParams, Link } from 'react-router';
import {
  useWorkflowDefinitionsGetWorkflowDefinition,
  useWorkflowDefinitionsCreateWorkflowDefinition,
  useWorkflowDefinitionsUpdateWorkflowDefinition,
} from '@/generated/api/workflow-definitions/workflow-definitions';
import {
  useModelsListModels,
  useModelsListAllAssignments,
  useModelsCreateModelAssignment,
  useModelsDeleteModelAssignment,
} from '@/generated/api/models/models';
import { AgentStepNode } from '../components/nodes/AgentStepNode';
import { ApprovalGateNode } from '../components/nodes/ApprovalGateNode';

const nodeTypes = {
  agentStep: AgentStepNode,
  approvalGate: ApprovalGateNode,
} as const;

const roles = ['system', 'human', 'planner', 'coder', 'reviewer', 'architect', 'qa', 'security', 'devops', 'tech_lead', 'documentation', 'triage', 'pm', 'designer', 'summarizer'];

const initialNodes: Node[] = [
  { id: 'ingest', type: 'agentStep', position: { x: 0, y: 150 }, data: { label: 'Ingest', role: 'pm' } },
  { id: 'route', type: 'agentStep', position: { x: 220, y: 150 }, data: { label: 'Route', role: 'planner' } },
  { id: 'plan', type: 'agentStep', position: { x: 440, y: 150 }, data: { label: 'Plan', role: 'planner' } },
  { id: 'approve_spec', type: 'approvalGate', position: { x: 660, y: 150 }, data: { label: 'Approve Spec' } },
  { id: 'implement', type: 'agentStep', position: { x: 880, y: 150 }, data: { label: 'Implement', role: 'coder' } },
  { id: 'review', type: 'agentStep', position: { x: 1100, y: 150 }, data: { label: 'Review', role: 'reviewer' } },
  { id: 'approve_merge', type: 'approvalGate', position: { x: 1320, y: 150 }, data: { label: 'Approve Merge' } },
  { id: 'close', type: 'agentStep', position: { x: 1540, y: 150 }, data: { label: 'Close', role: 'pm' } },
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
  const { id } = useParams<{ id: string }>();
  const { data: defResp, isLoading } = useWorkflowDefinitionsGetWorkflowDefinition(id ?? '', {
    query: { enabled: !!id },
  });
  const createMut = useWorkflowDefinitionsCreateWorkflowDefinition();
  const updateMut = useWorkflowDefinitionsUpdateWorkflowDefinition();
  const { data: modelsResp } = useModelsListModels();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const modelOptions = ((modelsResp?.data ?? []) as Array<Record<string, any>>).map((m) => ({
    value: m.model_id as string,
    label: (m.name ?? m.model_name) as string,
  }));
  const { data: allAssignmentsResp } = useModelsListAllAssignments();
  const createAssignMut = useModelsCreateModelAssignment();
  const deleteAssignMut = useModelsDeleteModelAssignment();
  const qc = useQueryClient();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const allAssignments = (allAssignmentsResp?.data ?? []) as Array<Record<string, any>>;
  // Build a lookup: step name → { model_id, assignment_id } for pipeline_step context
  const stepAssignments = new Map<string, { model_id: string; assignment_id: string }>();
  for (const a of allAssignments) {
    if (a.context === 'pipeline_step' || a.context === 'workflow_step') {
      stepAssignments.set(a.context_id as string, {
        model_id: a.model_id as string,
        assignment_id: a.assignment_id as string,
      });
    }
  }

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [loaded, setLoaded] = useState(false);

  // Load existing workflow definition
  useEffect(() => {
    if (loaded || !defResp?.data) return;
    const def = defResp.data as Record<string, unknown>;
    if (def.name) setWorkflowName(String(def.name));
    const graph = def.graph as Record<string, unknown> | undefined;
    if (graph?.nodes) {
      const rawNodes = graph.nodes as unknown[];
      // Check if nodes are ReactFlow format (objects with id/position) or backend format (strings)
      if (rawNodes.length > 0 && typeof rawNodes[0] === 'object' && rawNodes[0] !== null && 'position' in (rawNodes[0] as Record<string, unknown>)) {
        setNodes(rawNodes as Node[]);
      } else {
        // Convert string node IDs to ReactFlow nodes
        const approvalKeywords = ['approval', 'gate', 'approve'];
        const meta = (graph.node_metadata ?? {}) as Record<string, { label?: string; agent?: string; agent_id?: string; model_id?: string; description?: string }>;
        const converted: Node[] = (rawNodes as string[]).map((nodeId, i) => {
          const id = String(nodeId);
          const nm = meta[id];
          return {
            id,
            type: approvalKeywords.some((k) => id.includes(k)) ? 'approvalGate' : 'agentStep',
            position: { x: i * 220, y: 150 },
            data: {
              label: nm?.label ?? id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
              role: nm?.agent ?? 'coder',
              agent_id: nm?.agent_id ?? '',
              model_id: nm?.model_id ?? '',
              description: nm?.description ?? '',
            },
          };
        });
        setNodes(converted);
      }

      const rawEdges = graph.edges as unknown[];
      if (rawEdges?.length > 0) {
        if (Array.isArray(rawEdges[0]) && typeof (rawEdges[0] as unknown[])[0] === 'string') {
          // Backend format: [["a", "b"], ...]
          setEdges((rawEdges as string[][]).map(([src, tgt]) => ({
            id: `e-${src}-${tgt}`, source: src!, target: tgt!,
          })));
        } else {
          // ReactFlow format: [{id, source, target}, ...]
          setEdges(rawEdges as { id: string; source: string; target: string }[]);
        }
      }
    }
    setLoaded(true);
  }, [defResp, loaded, setNodes, setEdges]);

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
    const maxX = nodes.reduce((max, n) => Math.max(max, n.position.x), 0);
    const newNode: Node = {
      id,
      type,
      position: { x: maxX + 220, y: 150 },
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

  if (id && isLoading) return <Center py="xl"><Loader /></Center>;

  const handleSave = () => {
    const graph = {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data })),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    };

    if (id) {
      updateMut.mutate(
        { definitionId: id, data: { name: workflowName, graph } },
        {
          onSuccess: () => notifications.show({ title: 'Saved', message: 'Workflow updated', color: 'green' }),
          onError: () => notifications.show({ title: 'Error', message: 'Failed to save', color: 'red' }),
        },
      );
    } else {
      createMut.mutate(
        { data: { name: workflowName, graph } },
        {
          onSuccess: () => notifications.show({ title: 'Created', message: 'Workflow created', color: 'green' }),
          onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
        },
      );
    }
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
            <Stack gap="xs">
              <TextInput
                size="xs"
                placeholder="Workflow name"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.currentTarget.value)}
                style={{ width: 200 }}
              />
              <Group gap="xs">
                <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => addNode('agentStep')}>
                  Agent Step
                </Button>
                <Button size="xs" leftSection={<IconPlus size={14} />} variant="light" onClick={() => addNode('approvalGate')}>
                  Approval Gate
                </Button>
                <Button size="xs" variant="filled" color="green" onClick={handleSave} loading={updateMut.isPending || createMut.isPending}>
                  Save
                </Button>
              </Group>
            </Stack>
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
                label="Agent"
                data={roles}
                value={String(selectedNode.data.role ?? '')}
                onChange={(v) => v && updateNodeData('role', v)}
              />
            )}
            <Select
              label="Model"
              data={modelOptions}
              value={stepAssignments.get(selectedNode.id)?.model_id ?? null}
              onChange={(newModelId) => {
                const existing = stepAssignments.get(selectedNode.id);
                // Remove old assignment if exists
                if (existing) {
                  deleteAssignMut.mutate({ assignmentId: existing.assignment_id }, {
                    onSuccess: () => {
                      void qc.invalidateQueries({ queryKey: ['/api/v1/model-assignments'] });
                      if (newModelId) {
                        createAssignMut.mutate({
                          modelId: newModelId,
                          data: { context: 'pipeline_step' as const, context_id: selectedNode.id, priority: 0 },
                        }, {
                          onSuccess: () => {
                            void qc.invalidateQueries({ queryKey: ['/api/v1/model-assignments'] });
                            notifications.show({ title: 'Updated', message: 'Model assignment updated', color: 'green' });
                          },
                        });
                      } else {
                        notifications.show({ title: 'Removed', message: 'Model assignment removed', color: 'orange' });
                      }
                    },
                  });
                } else if (newModelId) {
                  createAssignMut.mutate({
                    modelId: newModelId,
                    data: { context: 'pipeline_step' as const, context_id: selectedNode.id, priority: 0 },
                  }, {
                    onSuccess: () => {
                      void qc.invalidateQueries({ queryKey: ['/api/v1/model-assignments'] });
                      notifications.show({ title: 'Assigned', message: 'Model assigned to step', color: 'green' });
                    },
                  });
                }
              }}
              placeholder="Default (no override)"
              clearable
              searchable
            />
            {!!selectedNode.data.agent_id && (
              <Text size="xs">
                Agent:{' '}
                <Text component={Link} to={`/agents/${selectedNode.data.agent_id}`} size="xs" c="blue" td="underline" span>
                  {String(selectedNode.data.role)}
                </Text>
              </Text>
            )}
            {!!selectedNode.data.description && (
              <Paper p="xs" bg="var(--mantine-color-body)" radius="sm" withBorder>
                <Text size="xs" fw={500} mb={4}>Description</Text>
                <Text size="xs" c="dimmed">{String(selectedNode.data.description)}</Text>
              </Paper>
            )}
          </Stack>
        </Paper>
      )}
    </div>
  );
}
