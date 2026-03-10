import { useCallback, useMemo } from 'react';
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
import {
  IconCircleCheck,
  IconCircleX,
  IconLoader2,
  IconClock,
  IconCircleDashed,
  IconPlayerPause,
  IconShieldCheck,
  IconMessageCircle,
  IconGitBranch,
  IconWebhook,
  IconClockHour4,
  IconUser,
  IconBolt,
  IconLink,
  IconChecks,
  IconFileText,
  IconGitPullRequest,
  IconCode,
  IconListCheck,
} from '@tabler/icons-react';
import '@xyflow/react/dist/style.css';

// ── Props ────────────────────────────────────────────────────────────────────

export interface DAGNode {
  id: string;
  type: string; // 'agentStep' | 'approvalGate' | 'trigger' | 'output' | 'artifact'
  label: string;
  status?: string;
  version?: string;
  meta?: Record<string, unknown>; // extra data for trigger/output/artifact nodes
}

export interface DAGEdge {
  source: string;
  target: string;
  constraint?: 'passed' | 'trigger';
  label?: string;
}

interface PipelineDAGProps {
  nodes: DAGNode[];
  edges: DAGEdge[];
  onNodeClick?: (nodeId: string) => void;
  /** Max columns before wrapping to next row. Defaults to 4. */
  maxCols?: number;
}

// ── Status config ────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, {
  icon: React.ElementType;
  color: string;
  bg: string;
  border: string;
  glow?: string;
}> = {
  succeeded: {
    icon: IconCircleCheck,
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.08)',
    border: 'rgba(34, 197, 94, 0.3)',
  },
  approved: {
    icon: IconShieldCheck,
    color: '#14b8a6',
    bg: 'rgba(20, 184, 166, 0.08)',
    border: 'rgba(20, 184, 166, 0.3)',
  },
  failed: {
    icon: IconCircleX,
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.08)',
    border: 'rgba(239, 68, 68, 0.3)',
  },
  rejected: {
    icon: IconCircleX,
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.08)',
    border: 'rgba(239, 68, 68, 0.3)',
  },
  running: {
    icon: IconLoader2,
    color: '#3b82f6',
    bg: 'rgba(59, 130, 246, 0.1)',
    border: 'rgba(59, 130, 246, 0.5)',
    glow: '0 0 12px rgba(59, 130, 246, 0.3)',
  },
  waiting_approval: {
    icon: IconPlayerPause,
    color: '#eab308',
    bg: 'rgba(234, 179, 8, 0.08)',
    border: 'rgba(234, 179, 8, 0.4)',
    glow: '0 0 10px rgba(234, 179, 8, 0.2)',
  },
  pending: {
    icon: IconClock,
    color: '#6b7280',
    bg: 'rgba(107, 114, 128, 0.05)',
    border: 'rgba(107, 114, 128, 0.2)',
  },
  skipped: {
    icon: IconCircleDashed,
    color: '#6b7280',
    bg: 'rgba(107, 114, 128, 0.05)',
    border: 'rgba(107, 114, 128, 0.2)',
  },
  cancelled: {
    icon: IconCircleX,
    color: '#f97316',
    bg: 'rgba(249, 115, 22, 0.08)',
    border: 'rgba(249, 115, 22, 0.3)',
  },
};

const DEFAULT_STATUS = STATUS_CONFIG.pending!;

// ── Trigger icons ────────────────────────────────────────────────────────────

const TRIGGER_ICONS: Record<string, React.ElementType> = {
  chat: IconMessageCircle,
  git: IconGitBranch,
  webhook: IconWebhook,
  schedule: IconClockHour4,
  manual: IconUser,
};

// ── Output icons ─────────────────────────────────────────────────────────────

const OUTPUT_ICONS: Record<string, React.ElementType> = {
  pr_url: IconGitPullRequest,
  verdict: IconChecks,
};

// ── Custom nodes ─────────────────────────────────────────────────────────────

interface StageNodeData {
  label: string;
  status: string;
  nodeType: string;
  artifacts?: string[];
  [key: string]: unknown;
}

const ARTIFACT_BADGE: Record<string, { icon: React.ElementType; label: string }> = {
  report: { icon: IconFileText, label: 'Report' },
  plan: { icon: IconListCheck, label: 'Plan' },
  diff: { icon: IconCode, label: 'Diff' },
  review: { icon: IconChecks, label: 'Review' },
};

function StageNode({ data, selected }: NodeProps & { data: StageNodeData }) {
  const cfg = STATUS_CONFIG[data.status] ?? DEFAULT_STATUS;
  const Icon = cfg.icon;
  const isRunning = data.status === 'running';
  const isApprovalGate = data.nodeType === 'approvalGate';
  const artifacts = (data.artifacts ?? []) as string[];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: '10px 16px',
        borderRadius: isApprovalGate ? 24 : 10,
        background: cfg.bg,
        border: `1.5px solid ${selected ? cfg.color : cfg.border}`,
        boxShadow: selected
          ? `0 0 0 2px ${cfg.color}40`
          : cfg.glow ?? 'none',
        minWidth: 140,
        cursor: 'pointer',
        transition: 'all 150ms ease',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: cfg.border, border: 'none', width: 6, height: 6 }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Icon
          size={18}
          color={cfg.color}
          stroke={1.8}
          style={isRunning ? { animation: 'spin 1.2s linear infinite' } : undefined}
        />
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--mantine-color-text)', whiteSpace: 'nowrap' }}>
          {data.label}
        </span>
      </div>
      {artifacts.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginLeft: 28 }}>
          {artifacts.map((a) => {
            const badge = ARTIFACT_BADGE[a];
            if (!badge) return null;
            const BadgeIcon = badge.icon;
            return (
              <div
                key={a}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 3,
                  padding: '1px 6px',
                  borderRadius: 4,
                  background: 'rgba(139, 92, 246, 0.08)',
                  border: '1px solid rgba(139, 92, 246, 0.2)',
                }}
              >
                <BadgeIcon size={10} color="#a78bfa" stroke={1.8} />
                <span style={{ fontSize: 9, color: '#a78bfa', fontWeight: 500 }}>{badge.label}</span>
              </div>
            );
          })}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: cfg.border, border: 'none', width: 6, height: 6 }}
      />
    </div>
  );
}

// ── Trigger node (pill, amber, left edge — source only) ──────────────────────

interface TriggerNodeData {
  label: string;
  triggerKind: string;
  [key: string]: unknown;
}

function TriggerNode({ data }: NodeProps & { data: TriggerNodeData }) {
  const Icon = TRIGGER_ICONS[data.triggerKind] ?? IconBolt;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 16px',
        borderRadius: 20,
        background: 'rgba(234, 179, 8, 0.10)',
        border: '1.5px solid rgba(234, 179, 8, 0.4)',
        cursor: 'default',
      }}
    >
      <Icon size={16} color="#eab308" stroke={1.8} />
      <span style={{ fontSize: 12, fontWeight: 600, color: '#eab308', whiteSpace: 'nowrap' }}>
        {data.label}
      </span>
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: 'rgba(234,179,8,0.4)', border: 'none', width: 6, height: 6 }}
      />
    </div>
  );
}

// ── Output node (pill, teal, right edge — target only) ───────────────────────

interface OutputNodeData {
  label: string;
  outputKind: string;
  [key: string]: unknown;
}

function OutputNode({ data }: NodeProps & { data: OutputNodeData }) {
  const Icon = OUTPUT_ICONS[data.outputKind] ?? IconLink;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 14px',
        borderRadius: 20,
        background: 'rgba(20, 184, 166, 0.10)',
        border: '1.5px solid rgba(20, 184, 166, 0.35)',
        cursor: 'default',
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: 'rgba(20,184,166,0.4)', border: 'none', width: 6, height: 6 }}
      />
      <Icon size={16} color="#14b8a6" stroke={1.8} />
      <span style={{ fontSize: 12, fontWeight: 500, color: '#14b8a6', whiteSpace: 'nowrap' }}>
        {data.label}
      </span>
    </div>
  );
}

const nodeTypes = {
  stageNode: StageNode,
  triggerNode: TriggerNode,
  outputNode: OutputNode,
};

// ── Layout ───────────────────────────────────────────────────────────────────

const STAGE_W = 200;
const STAGE_H = 44;
const GAP_X = 60;
const ROW_GAP_Y = 90;

/**
 * Layout all nodes in a wrapping left-to-right flow.
 *
 * The "flow" items are: [trigger, ...stages, ...outputs] laid out sequentially.
 * When a row reaches `maxCols`, the next node wraps to a new row.
 */
function layoutAll(inputNodes: DAGNode[], maxCols: number): Node[] {
  const triggers = inputNodes.filter((n) => n.type === 'trigger');
  const stages = inputNodes.filter((n) => n.type !== 'trigger' && n.type !== 'output');
  const outputs = inputNodes.filter((n) => n.type === 'output');

  const flowItems = [...triggers, ...stages, ...outputs];
  const result: Node[] = [];

  for (let i = 0; i < flowItems.length; i++) {
    const n = flowItems[i]!;
    const col = i % maxCols;
    const row = Math.floor(i / maxCols);
    const x = col * (STAGE_W + GAP_X);
    const y = row * ROW_GAP_Y;

    if (n.type === 'trigger') {
      result.push({
        id: n.id,
        type: 'triggerNode',
        position: { x, y: y + STAGE_H / 2 },
        data: { label: n.label, triggerKind: (n.meta?.triggerKind as string) ?? 'manual' },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    } else if (n.type === 'output') {
      result.push({
        id: n.id,
        type: 'outputNode',
        position: { x, y: y + STAGE_H / 2 },
        data: { label: n.label, outputKind: (n.meta?.outputKind as string) ?? 'link' },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    } else {
      result.push({
        id: n.id,
        type: 'stageNode',
        position: { x, y },
        data: {
          label: n.version ? `${n.label} ${n.version}` : n.label,
          status: n.status ?? 'pending',
          nodeType: n.type,
          artifacts: (n.meta?.artifacts as string[]) ?? [],
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    }
  }

  return result;
}

// ── Component ────────────────────────────────────────────────────────────────

export function PipelineDAG({ nodes: inputNodes, edges: inputEdges, onNodeClick, maxCols = 4 }: PipelineDAGProps) {
  const nodes = useMemo(() => layoutAll(inputNodes, maxCols), [inputNodes, maxCols]);

  // Compute height based on number of rows
  const flowCount = inputNodes.length;
  const rows = Math.ceil(flowCount / maxCols);
  const dynamicHeight = Math.max(200, rows * ROW_GAP_Y + 80);

  const edges: Edge[] = useMemo(
    () =>
      inputEdges.map((e, i) => {
        const sourceNode = inputNodes.find((n) => n.id === e.source);
        const isActive = sourceNode?.status === 'running';
        const isTrigger = e.constraint === 'trigger';
        const isPassed = e.constraint === 'passed';

        const edgeColor = isTrigger
          ? '#eab308'
          : sourceNode?.type === 'trigger'
            ? '#eab30880'
            : '#4b5563';

        return {
          id: `e-${i}`,
          source: e.source,
          target: e.target,
          label: e.label,
          animated: isActive,
          type: 'smoothstep',
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: edgeColor,
            width: 14,
            height: 10,
          },
          style: {
            stroke: edgeColor,
            strokeWidth: isTrigger || isActive ? 2 : 1.5,
            strokeDasharray: isPassed ? '6 4' : undefined,
            opacity: isPassed ? 0.4 : 0.7,
          },
          labelStyle: {
            fontSize: 11,
            fill: '#eab308',
            fontWeight: 500,
          },
          labelBgStyle: {
            fill: 'var(--mantine-color-body)',
            fillOpacity: 0.8,
          },
        };
      }),
    [inputEdges, inputNodes],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  return (
    <div style={{ height: dynamicHeight, width: '100%' }}>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .react-flow__node:hover {
          filter: brightness(1.1);
        }
      `}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.5 }}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(255,255,255,0.03)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
