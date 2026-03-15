import { useMemo, useState, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeProps,
  Position,
  MarkerType,
  Handle,
  BackgroundVariant,
} from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import { Drawer, Stack, Text, Title, Badge, Group, Paper } from '@mantine/core';
import '@xyflow/react/dist/style.css';

import type { ServiceNode, IntegrationEdge } from '../types';
import { INTEGRATION_TYPE_COLORS } from '../types';

// ── Props ───────────────────────────────────────────────────────────────────

interface ServiceDependencyGraphProps {
  nodes: ServiceNode[];
  edges: IntegrationEdge[];
}

// ── Dagre layout ────────────────────────────────────────────────────────────

const NODE_WIDTH = 180;
const NODE_HEIGHT = 60;

function layoutGraph(
  serviceNodes: ServiceNode[],
  integrationEdges: IntegrationEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 100 });

  for (const sn of serviceNodes) {
    g.setNode(sn.node_id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const ie of integrationEdges) {
    g.setEdge(ie.source_node_id, ie.target_node_id);
  }

  dagre.layout(g);

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
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  const flowEdges: Edge[] = integrationEdges.map((ie) => {
    const color = INTEGRATION_TYPE_COLORS[ie.integration_type] ?? '#868e96';
    return {
      id: ie.edge_id,
      source: ie.source_node_id,
      target: ie.target_node_id,
      type: 'smoothstep',
      animated: ie.integration_type === 'async',
      label: `${ie.integration_type} (${ie.protocol})`,
      labelStyle: { fontSize: 10, fill: color, fontWeight: 500 },
      labelBgStyle: {
        fill: 'var(--mantine-color-body)',
        fillOpacity: 0.85,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 14,
        height: 10,
      },
      style: { stroke: color, strokeWidth: 2 },
    };
  });

  return { nodes: flowNodes, edges: flowEdges };
}

// ── Custom service node ─────────────────────────────────────────────────────

interface ServiceNodeData {
  serviceName: string;
  language: string;
  metadata: Record<string, unknown>;
  [key: string]: unknown;
}

function ServiceNodeComponent({ data }: NodeProps & { data: ServiceNodeData }) {
  return (
    <div
      style={{
        padding: '10px 16px',
        borderRadius: 10,
        background: 'var(--mantine-color-dark-6, #f8f9fa)',
        border: '1.5px solid var(--mantine-color-dark-4, #dee2e6)',
        minWidth: 140,
        cursor: 'pointer',
        transition: 'all 150ms ease',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#868e96', border: 'none', width: 6, height: 6 }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--mantine-color-text)',
            whiteSpace: 'nowrap',
          }}
        >
          {data.serviceName}
        </span>
        <span style={{ fontSize: 11, color: 'var(--mantine-color-dimmed)' }}>
          {data.language}
        </span>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: '#868e96', border: 'none', width: 6, height: 6 }}
      />
    </div>
  );
}

const nodeTypes = { serviceNode: ServiceNodeComponent };

// ── Legend ───────────────────────────────────────────────────────────────────

function Legend() {
  return (
    <Paper
      p="xs"
      radius="sm"
      withBorder
      style={{
        position: 'absolute',
        bottom: 50,
        right: 10,
        zIndex: 5,
      }}
    >
      <Text size="xs" fw={600} mb={4}>
        Integration Types
      </Text>
      <Stack gap={2}>
        {Object.entries(INTEGRATION_TYPE_COLORS).map(([type, color]) => (
          <Group key={type} gap="xs">
            <div
              style={{
                width: 20,
                height: 3,
                borderRadius: 2,
                background: color,
              }}
            />
            <Text size="xs" tt="capitalize">
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

  return (
    <div style={{ height: 500, width: '100%', position: 'relative' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
        nodesDraggable
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
              <Text size="sm" ff="monospace">
                {selectedNode.node_id}
              </Text>
            </div>
            {Object.keys(selectedNode.metadata).length > 0 && (
              <div>
                <Text size="xs" c="dimmed" mb={4}>
                  Metadata
                </Text>
                <Paper withBorder p="sm" radius="sm">
                  <pre
                    style={{
                      fontSize: 12,
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
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
