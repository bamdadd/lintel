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
  IconDatabase,
  IconCloud,
  IconArrowsExchange,
  IconFile,
  IconBolt,
} from '@tabler/icons-react';
import '@xyflow/react/dist/style.css';

import type { ServiceNode, IntegrationEdge } from '../types';
import { INTEGRATION_TYPE_COLORS } from '../types';

// ── Props ───────────────────────────────────────────────────────────────────

interface ServiceDependencyGraphProps {
  nodes: ServiceNode[];
  edges: IntegrationEdge[];
}

// ── Dagre layout ────────────────────────────────────────────────────────────

const NODE_WIDTH = 200;
const NODE_HEIGHT = 72;

function layoutGraph(
  serviceNodes: ServiceNode[],
  integrationEdges: IntegrationEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: 'LR',
    nodesep: 50,
    ranksep: 140,
    marginx: 30,
    marginy: 30,
  });

  for (const sn of serviceNodes) {
    g.setNode(sn.node_id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const ie of integrationEdges) {
    g.setEdge(ie.source_node_id, ie.target_node_id);
  }

  dagre.layout(g);

  // Count incoming edges per node for visual weight
  const inDegree = new Map<string, number>();
  for (const ie of integrationEdges) {
    inDegree.set(ie.target_node_id, (inDegree.get(ie.target_node_id) ?? 0) + 1);
  }

  const flowNodes: Node[] = serviceNodes.map((sn) => {
    const pos = g.node(sn.node_id);
    return {
      id: sn.node_id,
      type: 'serviceNode',
      position: {
        x: (pos?.x ?? 0) - NODE_WIDTH / 2,
        y: (pos?.y ?? 0) - NODE_HEIGHT / 2,
      },
      data: {
        serviceName: sn.service_name,
        language: sn.language,
        metadata: sn.metadata,
        inDegree: inDegree.get(sn.node_id) ?? 0,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  // Deduplicate edges: collapse multiple edges between the same pair into one
  // with a combined label showing all types
  const edgeMap = new Map<string, { types: Set<string>; protocols: Set<string>; edge: IntegrationEdge }>();
  for (const ie of integrationEdges) {
    const key = `${ie.source_node_id}→${ie.target_node_id}`;
    const existing = edgeMap.get(key);
    if (existing) {
      existing.types.add(ie.integration_type || 'sync');
      existing.protocols.add(ie.protocol);
    } else {
      edgeMap.set(key, {
        types: new Set([ie.integration_type || 'sync']),
        protocols: new Set([ie.protocol]),
        edge: ie,
      });
    }
  }

  const flowEdges: Edge[] = Array.from(edgeMap.values()).map(({ types, protocols, edge }) => {
    // Use the "most important" type for coloring: external > database > async > sync > file
    const typePriority = ['external', 'database', 'async', 'sync', 'file'];
    const primaryType = typePriority.find((t) => types.has(t)) ?? 'sync';
    const color = INTEGRATION_TYPE_COLORS[primaryType] ?? '#868e96';

    // Build label: show protocols, not types (types are shown via color)
    const protocolList = Array.from(protocols).filter((p) => p && p !== 'unknown');
    const label = protocolList.length > 0 ? protocolList.join(', ') : primaryType;

    return {
      id: edge.edge_id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      type: 'smoothstep',
      animated: types.has('async'),
      label,
      labelStyle: { fontSize: 10, fill: '#c1c2c5', fontWeight: 500, letterSpacing: 0.3 },
      labelBgStyle: {
        fill: 'var(--mantine-color-dark-7, #1a1b1e)',
        fillOpacity: 0.92,
        rx: 4,
        ry: 4,
      },
      labelBgPadding: [6, 4] as [number, number],
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 16,
        height: 12,
      },
      style: { stroke: color, strokeWidth: 2 },
    };
  });

  return { nodes: flowNodes, edges: flowEdges };
}

// ── Integration type icon ───────────────────────────────────────────────────

const TYPE_ICONS: Record<string, React.ReactNode> = {
  sync: <IconArrowsExchange size={14} />,
  async: <IconBolt size={14} />,
  database: <IconDatabase size={14} />,
  file: <IconFile size={14} />,
  external: <IconCloud size={14} />,
};

// ── Custom service node ─────────────────────────────────────────────────────

interface ServiceNodeData {
  serviceName: string;
  language: string;
  metadata: Record<string, unknown>;
  inDegree: number;
  [key: string]: unknown;
}

function ServiceNodeComponent({ data }: NodeProps & { data: ServiceNodeData }) {
  // Determine a category for the icon based on node name
  const name = data.serviceName.toLowerCase();
  let icon: React.ReactNode = <IconArrowsExchange size={14} />;
  let badgeColor = 'gray';
  if (['postgres', 'redis', 'mongodb', 'elasticsearch', 'sqlalchemy', 'asyncpg', 'mysql'].some(k => name.includes(k))) {
    icon = <IconDatabase size={14} />;
    badgeColor = 'orange';
  } else if (['s3', 'blob', 'gcs', 'local_file', 'minio'].some(k => name.includes(k))) {
    icon = <IconFile size={14} />;
    badgeColor = 'gray';
  } else if (['kafka', 'nats', 'rabbitmq', 'celery', 'redis_pubsub'].some(k => name.includes(k))) {
    icon = <IconBolt size={14} />;
    badgeColor = 'green';
  } else if (['stripe', 'twilio', 'openai', 'aws', 'sendgrid', 'slack'].some(k => name.includes(k))) {
    icon = <IconCloud size={14} />;
    badgeColor = 'red';
  } else {
    badgeColor = 'blue';
  }

  return (
    <div
      style={{
        padding: '12px 16px',
        borderRadius: 12,
        background: 'var(--mantine-color-dark-6, #25262b)',
        border: `1.5px solid var(--mantine-color-dark-4, #373a40)`,
        minWidth: 160,
        cursor: 'pointer',
        transition: 'all 150ms ease',
        boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: INTEGRATION_TYPE_COLORS[badgeColor] ?? '#868e96',
          border: '2px solid var(--mantine-color-dark-6, #25262b)',
          width: 8,
          height: 8,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <ThemeIcon size="sm" variant="light" color={badgeColor} radius="sm">
          {icon}
        </ThemeIcon>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--mantine-color-text)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {data.serviceName}
          </span>
          <span style={{ fontSize: 10, color: 'var(--mantine-color-dimmed)', letterSpacing: 0.3 }}>
            {data.language}
          </span>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: INTEGRATION_TYPE_COLORS[badgeColor] ?? '#868e96',
          border: '2px solid var(--mantine-color-dark-6, #25262b)',
          width: 8,
          height: 8,
        }}
      />
    </div>
  );
}

const nodeTypes = { serviceNode: ServiceNodeComponent };

// ── Legend ───────────────────────────────────────────────────────────────────

function Legend() {
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
        Integration Types
      </Text>
      <Stack gap={4}>
        {Object.entries(INTEGRATION_TYPE_COLORS).map(([type, color]) => (
          <Group key={type} gap="xs">
            {TYPE_ICONS[type] ? (
              <ThemeIcon size="xs" variant="light" color={type === 'sync' ? 'blue' : type === 'async' ? 'green' : type === 'database' ? 'orange' : type === 'file' ? 'gray' : 'red'} radius="sm">
                {TYPE_ICONS[type]}
              </ThemeIcon>
            ) : (
              <div
                style={{
                  width: 20,
                  height: 3,
                  borderRadius: 2,
                  background: color,
                }}
              />
            )}
            <Text size="xs" tt="capitalize" c="dimmed">
              {type}
            </Text>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export function ServiceDependencyGraph({
  nodes: serviceNodes,
  edges: integrationEdges,
}: ServiceDependencyGraphProps) {
  const [selectedNode, setSelectedNode] = useState<ServiceNode | null>(null);

  const { nodes, edges } = useMemo(
    () => layoutGraph(serviceNodes, integrationEdges),
    [serviceNodes, integrationEdges],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const sn = serviceNodes.find((n) => n.node_id === node.id) ?? null;
      setSelectedNode(sn);
    },
    [serviceNodes],
  );

  // Find edges connected to the selected node for the detail drawer
  const selectedNodeEdges = useMemo(() => {
    if (!selectedNode) return { incoming: [] as IntegrationEdge[], outgoing: [] as IntegrationEdge[] };
    return {
      incoming: integrationEdges.filter((e) => e.target_node_id === selectedNode.node_id),
      outgoing: integrationEdges.filter((e) => e.source_node_id === selectedNode.node_id),
    };
  }, [selectedNode, integrationEdges]);

  return (
    <div style={{ height: 'calc(100vh - 280px)', minHeight: 400, width: '100%', position: 'relative' }}>
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

      <Drawer
        opened={selectedNode !== null}
        onClose={() => setSelectedNode(null)}
        title="Service Details"
        position="right"
        size="md"
      >
        {selectedNode && (
          <Stack gap="md">
            <div>
              <Text size="xs" c="dimmed">
                Service Name
              </Text>
              <Title order={4}>{selectedNode.service_name}</Title>
            </div>
            <Group>
              <div>
                <Text size="xs" c="dimmed">
                  Language
                </Text>
                <Badge variant="light">{selectedNode.language}</Badge>
              </div>
              <div>
                <Text size="xs" c="dimmed">
                  Node ID
                </Text>
                <Code>{selectedNode.node_id.slice(0, 12)}…</Code>
              </div>
            </Group>

            {selectedNodeEdges.outgoing.length > 0 && (
              <div>
                <Text size="xs" c="dimmed" mb={4} fw={600}>
                  Outgoing ({selectedNodeEdges.outgoing.length})
                </Text>
                <Stack gap={4}>
                  {selectedNodeEdges.outgoing.map((e) => {
                    const targetNode = serviceNodes.find(n => n.node_id === e.target_node_id);
                    return (
                      <Group key={e.edge_id} gap="xs">
                        <Badge size="xs" color={
                          e.integration_type === 'database' ? 'orange' :
                          e.integration_type === 'async' ? 'green' :
                          e.integration_type === 'external' ? 'red' :
                          e.integration_type === 'file' ? 'gray' : 'blue'
                        } variant="light">
                          {e.protocol}
                        </Badge>
                        <Text size="xs">→ {targetNode?.service_name ?? e.target_node_id.slice(0, 8)}</Text>
                      </Group>
                    );
                  })}
                </Stack>
              </div>
            )}

            {selectedNodeEdges.incoming.length > 0 && (
              <div>
                <Text size="xs" c="dimmed" mb={4} fw={600}>
                  Incoming ({selectedNodeEdges.incoming.length})
                </Text>
                <Stack gap={4}>
                  {selectedNodeEdges.incoming.map((e) => {
                    const sourceNode = serviceNodes.find(n => n.node_id === e.source_node_id);
                    return (
                      <Group key={e.edge_id} gap="xs">
                        <Badge size="xs" color={
                          e.integration_type === 'database' ? 'orange' :
                          e.integration_type === 'async' ? 'green' :
                          e.integration_type === 'external' ? 'red' :
                          e.integration_type === 'file' ? 'gray' : 'blue'
                        } variant="light">
                          {e.protocol}
                        </Badge>
                        <Text size="xs">← {sourceNode?.service_name ?? e.source_node_id.slice(0, 8)}</Text>
                      </Group>
                    );
                  })}
                </Stack>
              </div>
            )}

            {Object.keys(selectedNode.metadata).length > 0 && (
              <div>
                <Text size="xs" c="dimmed" mb={4} fw={600}>
                  Metadata
                </Text>
                <Paper withBorder p="sm" radius="sm">
                  <pre
                    style={{
                      fontSize: 11,
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: 'var(--mantine-color-dimmed)',
                    }}
                  >
                    {JSON.stringify(selectedNode.metadata, null, 2)}
                  </pre>
                </Paper>
              </div>
            )}
          </Stack>
        )}
      </Drawer>
    </div>
  );
}
