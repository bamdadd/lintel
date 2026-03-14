import { useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center, Tabs, ScrollArea, Box,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { IconArrowLeft, IconPlayerStop, IconLayoutList } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import {
  usePipelinesGetPipeline,
  usePipelinesListStages,
  usePipelinesCancelPipeline,
} from '@/generated/api/pipelines/pipelines';
import { PipelineDAG } from '../components/PipelineDAG';
import type { DAGNode, DAGEdge } from '../components/PipelineDAG';
import { StepTimingBar } from '../components/StepTimingBar';
import type { StageItem } from '../components/StageCard';
import { StageFullscreenModal } from '../components/StageCard';
import { StageListView } from '../components/StageListView';
import { usePipelineSSE } from '../hooks/usePipelineSSE';
import { getStatusColor } from '@/shared/components/StatusBadge';

export function Component() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const isMobile = useMediaQuery('(max-width: 768px)');

  // Sync expanded stage and artifacts modal with URL search params
  const selectedStageId = searchParams.get('stage') ?? null;
  const artifactParam = searchParams.get('artifact');
  const artifactsOpen = artifactParam !== null;

  const setSelectedStageId = useCallback((stageId: string | null) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (stageId) {
        next.set('stage', stageId);
      } else {
        next.delete('stage');
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const setArtifactsOpen = useCallback((open: boolean, tabKey?: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (open) {
        next.set('artifact', tabKey ?? '');
      } else {
        next.delete('artifact');
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const {
    data: pipelineResp,
    isLoading,
    refetch: refetchPipeline,
  } = usePipelinesGetPipeline(runId ?? '', {
    query: { staleTime: 0 },
  });
  const { data: stagesResp, refetch: refetchStages } = usePipelinesListStages(
    runId ?? '',
    { query: { enabled: !!runId, staleTime: 0 } },
  );

  // Real-time updates via SSE — refetch data on every stage/pipeline change
  const sse = usePipelineSSE(runId ?? null);
  useEffect(() => {
    sse.onUpdate(() => {
      refetchPipeline();
      refetchStages();
    });
  }, [sse.onUpdate, refetchPipeline, refetchStages]);

  const pipeline = (pipelineResp?.data ?? {}) as Record<string, unknown>;
  const stages = (stagesResp?.data ?? []) as StageItem[];
  const cancelMut = usePipelinesCancelPipeline();
  const handleActionComplete = useCallback(() => {
    refetchPipeline();
    refetchStages();
  }, [refetchPipeline, refetchStages]);

  const handleCancel = () => {
    cancelMut.mutate(
      { runId: runId! },
      {
        onSuccess: () => {
          notifications.show({ title: 'Cancelled', message: 'Pipeline cancelled', color: 'orange' });
          refetchPipeline();
          refetchStages();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to cancel pipeline', color: 'red' });
        },
      },
    );
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  // ── Build DAG nodes & edges ─────────────────────────────────────────────

  const mapStageType = (stageType: string | undefined): string => {
    if (!stageType) return 'agentStep';
    if (stageType.includes('approve') || stageType.includes('approval'))
      return 'approvalGate';
    return 'agentStep';
  };

  const dagNodes: DAGNode[] = [];
  const dagEdges: DAGEdge[] = [];

  // ── Trigger node (far left) ───────────────────────────────────────────
  const triggerType = pipeline.trigger_type as string | undefined;
  const triggerKind = triggerType?.startsWith('chat:')
    ? 'chat'
    : triggerType?.startsWith('work_item:')
      ? 'work_item'
      : triggerType?.startsWith('git:')
        ? 'git'
        : triggerType?.startsWith('webhook:')
          ? 'webhook'
          : triggerType?.startsWith('schedule:')
            ? 'schedule'
            : 'manual';
  const triggerLabel = triggerKind === 'chat'
    ? 'Chat'
    : triggerKind === 'work_item'
      ? 'Work Item'
      : triggerKind === 'git'
        ? 'Git Push'
        : triggerKind === 'webhook'
          ? 'Webhook'
          : triggerKind === 'schedule'
            ? 'Schedule'
            : 'Manual';

  const triggerId = '__trigger__';
  dagNodes.push({
    id: triggerId,
    type: 'trigger',
    label: triggerLabel,
    meta: { triggerKind },
  });

  // ── Stage nodes ───────────────────────────────────────────────────────
  const ARTIFACT_KEY_MAP: Record<string, string> = {
    research_report: 'report',
    plan: 'plan',
    diff: 'diff',
    review: 'review',
  };

  for (const s of stages) {
    const artifacts = s.outputs
      ? Object.keys(s.outputs)
          .filter((k) => k in ARTIFACT_KEY_MAP)
          .map((k) => ARTIFACT_KEY_MAP[k]!)
      : [];
    dagNodes.push({
      id: s.stage_id,
      type: mapStageType(s.stage_type),
      label: s.name,
      status: s.status,
      meta: artifacts.length > 0 ? { artifacts } : undefined,
    });
  }

  // ── Edges: trigger → first stage ──────────────────────────────────────
  if (stages.length > 0) {
    dagEdges.push({ source: triggerId, target: stages[0]!.stage_id });
  }

  // ── Edges: stage → stage (sequential) ─────────────────────────────────
  for (let i = 1; i < stages.length; i++) {
    dagEdges.push({
      source: stages[i - 1]!.stage_id,
      target: stages[i]!.stage_id,
    });
  }

  // ── Output nodes (terminal outputs from any stage with pr_url) ────────
  for (const s of stages) {
    if (s.outputs?.pr_url) {
      const prUrl = s.outputs.pr_url as string;
      const outputId = `__output_pr_${s.stage_id}`;
      dagNodes.push({
        id: outputId,
        type: 'output',
        label: `PR #${prUrl.split('/').pop()}`,
        meta: { outputKind: 'pr_url' },
      });
      dagEdges.push({ source: s.stage_id, target: outputId });
    }
  }

  const timingSteps = stages
    .filter((s) => s.started_at && s.finished_at)
    .map((s) => ({
      name: s.name,
      stepType: s.stage_type ?? 'agent',
      durationMs: s.duration_ms ?? 0,
      startMs: s.started_at ? new Date(s.started_at).getTime() : 0,
    }));

  return (
    <Stack gap="md">
      <Stack gap="xs">
        <Group gap="sm">
          <Button
            variant="subtle"
            size="compact-sm"
            leftSection={<IconArrowLeft size={14} />}
            onClick={() => navigate('/pipelines')}
          >
            Back
          </Button>
          <Title order={2}>Pipeline {runId?.slice(0, 8)}</Title>
          <Badge color={getStatusColor(pipeline.status as string)}>
            {(pipeline.status as string) ?? 'unknown'}
          </Badge>
        </Group>
        <Group gap="sm" wrap="wrap">
          {(pipeline.trigger_type as string)?.startsWith('chat:') && (
            <Button
              variant="light"
              size="compact-sm"
              onClick={() =>
                navigate(
                  `/chat/${(pipeline.trigger_type as string).slice(5)}`,
                )
              }
            >
              View Chat
            </Button>
          )}
          {(pipeline.work_item_id as string) && (
            <Button
              variant="light"
              size="compact-sm"
              color="indigo"
              onClick={async () => {
                try {
                  const resp = await fetch(`/api/v1/projects/${pipeline.project_id}/boards`);
                  const boards = await resp.json();
                  const boardId = boards?.[0]?.board_id;
                  if (boardId) {
                    navigate(`/boards/${boardId}?work_item=${pipeline.work_item_id}`);
                  } else {
                    navigate('/boards');
                  }
                } catch {
                  navigate('/boards');
                }
              }}
            >
              View Work Item
            </Button>
          )}
          {(pipeline.status === 'running' || pipeline.status === 'waiting_approval') && (
            <Button
              variant="light"
              size="compact-sm"
              color="orange"
              leftSection={<IconPlayerStop size={14} />}
              loading={cancelMut.isPending}
              onClick={handleCancel}
            >
              Cancel
            </Button>
          )}
          <Button
            variant="light"
            size="compact-sm"
            leftSection={<IconLayoutList size={14} />}
            onClick={() => setArtifactsOpen(true, 'first')}
          >
            Artifacts
          </Button>
          <Button
            variant="light"
            size="compact-sm"
            onClick={() => navigate(`/pipelines/runs/${runId}`)}
          >
            Event Log
          </Button>
        </Group>
      </Stack>

      {/* ── Two-column layout: DAG left, Steps right (steps only on mobile) ── */}
      <Box
        style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(0, 480px)',
          gap: 'var(--mantine-spacing-md)',
          minHeight: 0,
        }}
      >
        {/* ── Left: DAG + Timing tabs (hidden on mobile) ──────────────────── */}
        {!isMobile && (
          <Box style={{ minWidth: 0 }}>
            <Tabs defaultValue="dag">
              <Tabs.List>
                <Tabs.Tab value="dag">Pipeline DAG</Tabs.Tab>
                <Tabs.Tab value="timing">Step Timing</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="dag" pt="md">
                {dagNodes.length > 0 ? (
                  <PipelineDAG
                    nodes={dagNodes}
                    edges={dagEdges}
                    maxCols={3}
                    onNodeClick={(nodeId) =>
                      setSelectedStageId(
                        nodeId === selectedStageId ? null : nodeId,
                      )
                    }
                  />
                ) : (
                  <Paper withBorder p="md">
                    <Text c="dimmed">No stages to visualize</Text>
                  </Paper>
                )}
              </Tabs.Panel>

              <Tabs.Panel value="timing" pt="md">
                {timingSteps.length > 0 ? (
                  <StepTimingBar steps={timingSteps} />
                ) : (
                  <Paper withBorder p="md">
                    <Text c="dimmed">No timing data available</Text>
                  </Paper>
                )}
              </Tabs.Panel>
            </Tabs>
          </Box>
        )}

        {/* ── Steps panel (always visible, full width on mobile) ──────────── */}
        <Paper
          withBorder
          radius="md"
          style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
          <Group px="md" py="sm" style={(theme) => ({
            borderBottom: `1px solid ${theme.colors.dark[5]}`,
          })}>
            <Text fw={600} size="sm">Steps</Text>
            <Badge size="sm" variant="light">{stages.length}</Badge>
          </Group>
          <ScrollArea style={{ flex: 1 }} offsetScrollbars>
            <StageListView
              stages={stages}
              runId={runId!}
              selectedStageId={selectedStageId}
              onStageSelect={setSelectedStageId}
              onActionComplete={handleActionComplete}
              onOpenArtifact={(tabKey) => setArtifactsOpen(true, tabKey)}
            />
          </ScrollArea>
        </Paper>
      </Box>

      <StageFullscreenModal
        opened={artifactsOpen}
        onClose={() => setArtifactsOpen(false)}
        initialTabKey={artifactParam ?? undefined}
        onTabChange={(tabKey) => setArtifactsOpen(true, tabKey)}
        allStages={stages}
      />
    </Stack>
  );
}
