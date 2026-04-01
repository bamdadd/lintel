import type { Node, Edge } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';

// ── Backend data shapes (matching Python dataclasses) ─────────────────────

export interface PipelineRunData {
  run_id: string;
  project_id: string;
  work_item_id: string;
  workflow_definition_id: string;
  status: string;
  stages?: StageData[];
  trigger_type?: string;
  trigger_id?: string;
  trigger_context?: string;
  environment_id?: string;
  created_at?: string;
}

export interface StageData {
  stage_id: string;
  name: string;
  stage_type?: string;
  status: string;
  outputs?: Record<string, unknown>;
  error?: string;
  duration_ms?: number;
  started_at?: string;
  finished_at?: string;
  retry_count?: number;
}

export interface WorkflowGraph {
  nodes?: string[];
  edges?: [string, string][];
  conditional_edges?: Record<string, unknown>[];
  entry_point?: string;
  interrupt_before?: string[];
  node_metadata?: Record<string, { label?: string; description?: string; agent?: string }>;
}

export interface WorkflowDefinitionData {
  definition_id: string;
  name: string;
  graph?: WorkflowGraph;
  stage_names?: string[];
}

export interface ArtifactData {
  artifact_id: string;
  work_item_id: string;
  run_id: string;
  artifact_type: string;
  path?: string;
  content_type?: string;
  storage_backend?: string;
  size_bytes?: number;
}

// ── Trigger type mapping ──────────────────────────────────────────────────

function mapTriggerKind(triggerType?: string): string {
  if (!triggerType) return 'manual';
  if (triggerType.startsWith('chat')) return 'chat';
  if (triggerType.startsWith('work_item')) return 'work_item';
  if (triggerType.includes('git') || triggerType.includes('pr_event')) return 'git';
  if (triggerType.includes('webhook')) return 'webhook';
  if (triggerType.includes('schedule')) return 'schedule';
  if (triggerType.includes('slack')) return 'chat';
  return 'manual';
}

function triggerLabel(kind: string): string {
  const labels: Record<string, string> = {
    chat: 'Chat',
    work_item: 'Work Item',
    git: 'Git Push',
    webhook: 'Webhook',
    schedule: 'Schedule',
    manual: 'Manual',
  };
  return labels[kind] ?? 'Trigger';
}

// ── Transform pipeline data to React Flow nodes and edges ─────────────────

export function buildDagNodes(
  pipeline: PipelineRunData,
  stages: StageData[],
  _workflowDef?: WorkflowDefinitionData,
  _artifacts?: ArtifactData[],
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Trigger node (left edge)
  const triggerKind = mapTriggerKind(pipeline.trigger_type);
  const triggerId = '__trigger__';
  nodes.push({
    id: triggerId,
    type: 'trigger',
    position: { x: 0, y: 0 },
    data: {
      label: triggerLabel(triggerKind),
      triggerKind,
      timestamp: pipeline.created_at,
    },
  });

  // Build stage-to-stage edge map from workflow definition graph
  const graphEdges = _workflowDef?.graph?.edges;
  const stageNameToId = new Map<string, string>();
  for (const s of stages) {
    stageNameToId.set(s.name, s.stage_id);
  }

  // Stage nodes
  const ARTIFACT_KEYS = new Set(['research_report', 'plan', 'diff', 'review', 'report']);

  for (const stage of stages) {
    const artifactCount = stage.outputs
      ? Object.keys(stage.outputs).filter((k) => ARTIFACT_KEYS.has(k)).length
      : 0;

    nodes.push({
      id: stage.stage_id,
      type: 'stage',
      position: { x: 0, y: 0 },
      data: {
        name: stage.name,
        status: stage.status,
        durationMs: stage.duration_ms,
        artifactCount,
        stageType: stage.stage_type,
      },
    });
  }

  // Edges: use workflow graph if available, otherwise sequential
  if (graphEdges && graphEdges.length > 0) {
    // Map graph node names to stage IDs
    for (const [source, target] of graphEdges) {
      const sourceId = stageNameToId.get(source);
      const targetId = stageNameToId.get(target);
      if (sourceId && targetId) {
        edges.push(makeEdge(sourceId, targetId, stages));
      }
    }
    // Connect trigger to entry point
    const entryPoint = _workflowDef?.graph?.entry_point;
    const entryId = entryPoint ? stageNameToId.get(entryPoint) : stages[0]?.stage_id;
    if (entryId) {
      edges.push(makeTriggerEdge(triggerId, entryId));
    }
  } else {
    // Sequential fallback
    if (stages.length > 0) {
      edges.push(makeTriggerEdge(triggerId, stages[0]!.stage_id));
    }
    for (let i = 1; i < stages.length; i++) {
      edges.push(makeEdge(stages[i - 1]!.stage_id, stages[i]!.stage_id, stages));
    }
  }

  // Output nodes (PR URLs from stage outputs)
  for (const s of stages) {
    if (s.outputs?.pr_url) {
      const prUrl = s.outputs.pr_url as string;
      const outputId = `__output_pr_${s.stage_id}`;
      nodes.push({
        id: outputId,
        type: 'output',
        position: { x: 0, y: 0 },
        data: {
          label: `PR #${prUrl.split('/').pop()}`,
          outputKind: 'pr_url',
        },
      });
      edges.push(makeEdge(s.stage_id, outputId, stages));
    }
  }

  // Find terminal stages (no outgoing edges among stage nodes) and add output node
  const stageIds = new Set(stages.map((s) => s.stage_id));
  const hasOutgoing = new Set(edges.filter((e) => stageIds.has(e.target)).map((e) => e.source));
  const terminalStages = stages.filter(
    (s) => !hasOutgoing.has(s.stage_id) && !edges.some((e) => e.source === s.stage_id && e.target.startsWith('__output_')),
  );

  if (terminalStages.length > 0 && !nodes.some((n) => n.type === 'output')) {
    const outputId = '__output__';
    nodes.push({
      id: outputId,
      type: 'output',
      position: { x: 0, y: 0 },
      data: { label: 'Complete', outputKind: 'verdict' },
    });
    for (const ts of terminalStages) {
      edges.push(makeEdge(ts.stage_id, outputId, stages));
    }
  }

  return { nodes, edges };
}

function makeTriggerEdge(source: string, target: string): Edge {
  return {
    id: `e-${source}-${target}`,
    source,
    target,
    type: 'animated',
    style: { stroke: '#eab30880', strokeWidth: 2 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#eab308',
      width: 14,
      height: 10,
    },
  };
}

function makeEdge(source: string, target: string, stages: StageData[]): Edge {
  const sourceStage = stages.find((s) => s.stage_id === source);
  const isActive = sourceStage?.status === 'running';

  return {
    id: `e-${source}-${target}`,
    source,
    target,
    type: 'animated',
    animated: isActive,
    style: {
      stroke: '#4b5563',
      strokeWidth: 1.5,
      opacity: 0.7,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: '#4b5563',
      width: 14,
      height: 10,
    },
  };
}
