import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center, Tabs,
} from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import {
  usePipelinesGetPipeline,
  usePipelinesListStages,
} from '@/generated/api/pipelines/pipelines';
import { PipelineDAG } from '../components/PipelineDAG';
import { StepTimingBar } from '../components/StepTimingBar';

const statusColor: Record<string, string> = {
  pending: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
};

interface StageItem {
  stage_id: string;
  name: string;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  stage_type?: string;
}

export function Component() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { data: pipelineResp, isLoading } = usePipelinesGetPipeline(runId ?? '');
  const { data: stagesResp } = usePipelinesListStages(runId ?? '', {
    query: { enabled: !!runId },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const pipeline = (pipelineResp?.data ?? {}) as Record<string, unknown>;
  const stages = (stagesResp?.data ?? []) as StageItem[];

  const dagNodes = stages.map((s) => ({
    id: s.stage_id,
    type: s.stage_type ?? 'agentStep',
    label: s.name,
    status: s.status,
  }));

  const dagEdges = stages.slice(1).map((s, i) => ({
    source: stages[i].stage_id,
    target: s.stage_id,
  }));

  const timingSteps = stages
    .filter((s) => s.duration_ms)
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
            {pipeline.status as string ?? 'unknown'}
          </Badge>
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
              onNodeClick={(nodeId) => navigate(`/pipelines/runs/${runId}?step=${nodeId}`)}
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
    </Stack>
  );
}
