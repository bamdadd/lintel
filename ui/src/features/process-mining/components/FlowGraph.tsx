import { useMemo, useState, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Position,
  MarkerType,
  Handle,
  BackgroundVariant,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import {
  Drawer,
  Stack,
  Text,
  Title,
  Badge,
  Group,
  Paper,
  Code,
  ThemeIcon,
} from '@mantine/core';
import {
  IconApi,
  IconBolt,
  IconDatabase,
  IconCloud,
  IconArrowsShuffle,
  IconClock,
  IconLayersIntersect,
  IconTerminal2,
  IconShield,
} from '@tabler/icons-react';
import '@xyflow/react/dist/style.css';

import type { FlowEntry, FlowStep } from '../types';
import { FLOW_TYPE_COLORS, FLOW_TYPE_LABELS } from '../types';

// ── Props ──────────────────────────────────────────────────────────────────

interface FlowGraphProps {
  flows: FlowEntry[];
}

// ── Step type styling ──────────────────────────────────────────────────────

const STEP_COLORS: Record<string, string> = {
  entrypoint: '#228be6',
  middleware: '#868e96',
  handler: '#228be6',
  service: '#7950f2',
  store: '#fd7e14',
  database: '#fd7e14',
  event_bus: '#40c057',
  projection: '#12b886',
  external_api: '#fa5252',
  message_queue: '#40c057',
  scheduler: '#fab005',
};

const STEP_ICONS: Record<string, React.ReactNode> = {
  entrypoint: <IconApi size={14} />,
  middleware: <IconShield size={14} />,
  handler: <IconTerminal2 size={14} />,
  service: <IconLayersIntersect size={14} />,
  store: <IconDatabase size={14} />,
  database: <IconDatabase size={14} />,
  event_bus: <IconBolt size={14} />,
  projection: <IconLayersIntersect size={14} />,
  external_api: <IconCloud size={14} />,
  message_queue: <IconArrowsShuffle size={14} />,
  scheduler: <IconClock size={14} />,
};

// ── Dagre layout ───────────────────────────────────────────────────────────

const NODE_WIDTH = 220;
const NODE_HEIGHT = 64;

interface GraphNode {
  nodeId: string;
  label: string;
  stepType: string;
  filePath: string;
  lineNumber: number;
  description: string;
  flowType: string;
  flowName: string;
}

function buildGraph(flows: FlowEntry[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: 'LR',
    nodesep: 40,
    ranksep: 120,
    marginx: 30,
    marginy: 30,
  });

  const graphNodes = new Map<string, GraphNode>();
  const edgeSet = new Set<string>();
  const rawEdges: { source: string; target: string; flowType: string }[] = [];

  for (const flow of flows) {
    const allSteps: FlowStep[] = [
      flow.source,
      ...flow.steps,
      ...(flow.sink ? [flow.sink] : []),
    ];

    for (const step of allSteps) {
      // Unique by file:function:stepType
      const id = `${step.file_path}::${step.function_name}::${step.step_type}`;
      if (!graphNodes.has(id)) {
        graphNodes.set(id, {
          nodeId: id,
          label: step.function_name || step.step_type,
          stepType: step.step_type,
          filePath: step.file_path,
          lineNumber: step.line_number,
          description: step.description,
          flowType: flow.flow_type,
          flowName: flow.name,
        });
        g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT });
      }
    }

    // Create edges between consecutive steps
    for (let i = 0; i < allSteps.length - 1; i++) {
      const src = `${allSteps[i].file_path}::${allSteps[i].function_name}::${allSteps[i].step_type}`;
      const tgt = `${allSteps[i + 1].file_path}::${allSteps[i + 1].function_name}::${allSteps[i + 1].step_type}`;
      const key = `${src}→${tgt}`;
      if (!edgeSet.has(key) && src !== tgt) {
        edgeSet.add(key);
        rawEdges.push({ source: src, target: tgt, flowType: flow.flow_type });
      }
    }
  }

  dagre.layout(g);

  const flowNodes: Node[] = Array.from(graphNodes.values()).map((gn) => {
    const pos = g.node(gn.nodeId);
    return {
      id: gn.nodeId,
      type: 'flowStep',
      position: {
        x: (pos?.x ?? 0) - NODE_WIDTH / 2,
        y: (pos?.y ?? 0) - NODE_HEIGHT / 2,
      },
      data: gn,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  const flowEdges: Edge[] = rawEdges.map((re, i) => {
    const color = FLOW_TYPE_COLORS[re.flowType] ?? '#868e96';
    return {
      id: `e-${i}`,
      source: re.source,
      target: re.target,
      type: 'smoothstep',
      animated: re.flowType === 'event_sourcing' || re.flowType === 'background_job',
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 14,
        height: 10,
      },
      style: { stroke: color, strokeWidth: 1.5 },
    };
  });

  return { nodes: flowNodes, edges: flowEdges };
}

// ── Custom node ────────────────────────────────────────────────────────────

function FlowStepNode({ data }: NodeProps & { data: GraphNode }) {
  const color = STEP_COLORS[data.stepType] ?? '#868e96';
  const icon = STEP_ICONS[data.stepType] ?? <IconTerminal2 size={14} />;
  const mantineColor =
    data.stepType === 'entrypoint' || data.stepType === 'handler'
      ? 'blue'
      : data.stepType === 'store' || data.stepType === 'database'
        ? 'orange'
        : data.stepType === 'event_bus' || data.stepType === 'message_queue'
          ? 'green'
          : data.stepType === 'external_api'
            ? 'red'
            : data.stepType === 'projection'
              ? 'teal'
              : data.stepType === 'service'
                ? 'violet'
                : 'gray';

  return (
    <div
      style={{
        padding: '10px 14px',
        borderRadius: 10,
        background: 'var(--mantine-color-dark-6, #25262b)',
        border: `1.5px solid ${color}33`,
        minWidth: 160,
        maxWidth: NODE_WIDTH,
        cursor: 'pointer',
        transition: 'all 150ms ease',
        boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: color,
          border: '2px solid var(--mantine-color-dark-6, #25262b)',
          width: 7,
          height: 7,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <ThemeIcon size="sm" variant="light" color={mantineColor} radius="sm">
          {icon}
        </ThemeIcon>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--mantine-color-text)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {data.label}
          </span>
          <span
            style={{
              fontSize: 9,
              color: 'var(--mantine-color-dimmed)',
              letterSpacing: 0.3,
              textTransform: 'uppercase',
            }}
          >
            {data.stepType.replace(/_/g, ' ')}
          </span>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: color,
          border: '2px solid var(--mantine-color-dark-6, #25262b)',
          width: 7,
          height: 7,
        }}
      />
    </div>
  );
}

const nodeTypes = { flowStep: FlowStepNode };

// ── Legend ──────────────────────────────────────────────────────────────────

function Legend() {
  const items = [
    { label: 'Entrypoint', color: 'blue', icon: <IconApi size={12} /> },
    { label: 'Store / DB', color: 'orange', icon: <IconDatabase size={12} /> },
    { label: 'Event Bus', color: 'green', icon: <IconBolt size={12} /> },
    { label: 'External API', color: 'red', icon: <IconCloud size={12} /> },
    { label: 'Service', color: 'violet', icon: <IconLayersIntersect size={12} /> },
    { label: 'Projection', color: 'teal', icon: <IconLayersIntersect size={12} /> },
  ];
  return (
    <Paper
      p="sm"
      radius="md"
      withBorder
      style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        zIndex: 5,
        background: 'var(--mantine-color-dark-7, #1a1b1e)',
        borderColor: 'var(--mantine-color-dark-4, #373a40)',
      }}
    >
      <Text size="xs" fw={700} mb={6} tt="uppercase" c="dimmed" lts={0.5}>
        Step Types
      </Text>
      <Stack gap={4}>
        {items.map((item) => (
          <Group key={item.label} gap="xs">
            <ThemeIcon size="xs" variant="light" color={item.color} radius="sm">
              {item.icon}
            </ThemeIcon>
            <Text size="xs" c="dimmed">
              {item.label}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

// ── Edge legend ──────────────────────────────────────────────────────────────

function EdgeLegend() {
  return (
    <Paper
      p="sm"
      radius="md"
      withBorder
      style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        zIndex: 5,
        background: 'var(--mantine-color-dark-7, #1a1b1e)',
        borderColor: 'var(--mantine-color-dark-4, #373a40)',
      }}
    >
      <Text size="xs" fw={700} mb={6} tt="uppercase" c="dimmed" lts={0.5}>
        Flow Types
      </Text>
      <Stack gap={4}>
        {Object.entries(FLOW_TYPE_COLORS).map(([type, color]) => (
          <Group key={type} gap="xs">
            <div
              style={{
                width: 18,
                height: 3,
                borderRadius: 2,
                background: color,
              }}
            />
            <Text size="xs" c="dimmed">
              {FLOW_TYPE_LABELS[type] ?? type}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function FlowGraph({ flows }: FlowGraphProps) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const { nodes, edges } = useMemo(() => buildGraph(flows), [flows]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node.data as GraphNode);
    },
    [],
  );

  return (
    <div
      style={{
        height: 'calc(100vh - 300px)',
        minHeight: 400,
        width: '100%',
        position: 'relative',
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
        nodesDraggable
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="rgba(255,255,255,0.04)"
        />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={() => 'var(--mantine-color-dark-3)'}
          maskColor="rgba(0,0,0,0.6)"
          style={{ background: 'var(--mantine-color-dark-7, #1a1b1e)' }}
        />
      </ReactFlow>
      <Legend />
      <EdgeLegend />

      <Drawer
        opened={selectedNode !== null}
        onClose={() => setSelectedNode(null)}
        title="Flow Step Details"
        position="right"
        size="md"
      >
        {selectedNode && (
          <Stack gap="md">
            <div>
              <Text size="xs" c="dimmed">
                Function
              </Text>
              <Title order={4}>{selectedNode.label}</Title>
            </div>
            <Group>
              <div>
                <Text size="xs" c="dimmed">
                  Step Type
                </Text>
                <Badge
                  variant="light"
                  color={
                    selectedNode.stepType === 'entrypoint'
                      ? 'blue'
                      : selectedNode.stepType === 'store' ||
                          selectedNode.stepType === 'database'
                        ? 'orange'
                        : selectedNode.stepType === 'event_bus'
                          ? 'green'
                          : selectedNode.stepType === 'external_api'
                            ? 'red'
                            : 'gray'
                  }
                >
                  {selectedNode.stepType.replace(/_/g, ' ')}
                </Badge>
              </div>
              <div>
                <Text size="xs" c="dimmed">
                  Flow Type
                </Text>
                <Badge
                  variant="light"
                  color={FLOW_TYPE_COLORS[selectedNode.flowType] ?? 'gray'}
                >
                  {FLOW_TYPE_LABELS[selectedNode.flowType] ?? selectedNode.flowType}
                </Badge>
              </div>
            </Group>
            <div>
              <Text size="xs" c="dimmed">
                Location
              </Text>
              <Code>
                {selectedNode.filePath}:{selectedNode.lineNumber}
              </Code>
            </div>
            {selectedNode.description && (
              <div>
                <Text size="xs" c="dimmed">
                  Code
                </Text>
                <Paper withBorder p="sm" radius="sm">
                  <Code
                    block
                    style={{
                      fontSize: 11,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {selectedNode.description}
                  </Code>
                </Paper>
              </div>
            )}
            <div>
              <Text size="xs" c="dimmed">
                Flow
              </Text>
              <Text size="sm">{selectedNode.flowName}</Text>
            </div>
          </Stack>
        )}
      </Drawer>
    </div>
  );
}
