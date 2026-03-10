import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center, Tabs, Drawer,
} from '@mantine/core';
import { IconArrowLeft, IconX } from '@tabler/icons-react';
import {
  usePipelinesGetPipeline,
  usePipelinesListStages,
} from '@/generated/api/pipelines/pipelines';
import { PipelineDAG } from '../components/PipelineDAG';
import { StepTimingBar } from '../components/StepTimingBar';
import { StageCard } from '../components/StageCard';
import type { StageItem } from '../components/StageCard';
import { usePipelineSSE } from '../hooks/usePipelineSSE';

const statusColor: Record<string, string> = {
  pending: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
  skipped: 'gray',
  waiting_approval: 'yellow',
  approved: 'teal',
  rejected: 'red',
};

export function Component() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);

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
  const selectedStage = selectedStageId
    ? stages.find((s) => s.stage_id === selectedStageId) ?? null
    : null;

  const handleActionComplete = useCallback(() => {
    refetchPipeline();
    refetchStages();
  }, [refetchPipeline, refetchStages]);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const mapStageType = (stageType: string | undefined): string => {
    if (!stageType) return 'agentStep';
    if (stageType.includes('approve') || stageType.includes('approval'))
      return 'approvalGate';
    return 'agentStep';
  };

  const dagNodes = stages.map((s) => ({
    id: s.stage_id,
    type: mapStageType(s.stage_type),
    label: s.name,
    status: s.status,
  }));

  const dagEdges: Array<{ source: string; target: string; constraint?: 'passed' | 'trigger' }> =
    stages.slice(1).map((s, i) => ({
      source: stages[i]!.stage_id,
      target: s.stage_id,
    }));

  // Add review → implement loop edge if review requested changes
  const reviewStage = stages.find((s) => s.name === 'review');
  const implementStage = stages.find((s) => s.name === 'implement');
  if (
    reviewStage &&
    implementStage &&
    reviewStage.outputs?.verdict === 'request_changes' &&
    reviewStage.stage_id !== implementStage.stage_id
  ) {
    dagEdges.push({
      source: reviewStage.stage_id,
      target: implementStage.stage_id,
      constraint: 'trigger',
    });
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
      <Group justify="space-between">
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
          <Badge color={statusColor[pipeline.status as string] ?? 'gray'}>
            {(pipeline.status as string) ?? 'unknown'}
          </Badge>
        </Group>
        <Group gap="sm">
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
          <Button
            variant="light"
            size="compact-sm"
            onClick={() => navigate(`/pipelines/runs/${runId}`)}
          >
            Event Log
          </Button>
        </Group>
      </Group>

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

      <Drawer
        opened={!!selectedStage}
        onClose={() => setSelectedStageId(null)}
        position="right"
        size="xl"
        title={
          selectedStage ? (
            <Group gap="xs">
              <Text fw={600}>{selectedStage.name}</Text>
              <Badge color={statusColor[selectedStage.status] ?? 'gray'} size="sm">
                {selectedStage.status}
              </Badge>
            </Group>
          ) : null
        }
        overlayProps={{ backgroundOpacity: 0.1 }}
        closeButtonProps={{ icon: <IconX size={18} /> }}
      >
        {selectedStage && (
          <StageCard
            stage={selectedStage}
            runId={runId!}
            onActionComplete={handleActionComplete}
          />
        )}
      </Drawer>
    </Stack>
  );
}
