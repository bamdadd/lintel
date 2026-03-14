import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center,
} from '@mantine/core';
import { IconArrowLeft, IconPlayerPlay } from '@tabler/icons-react';
import { useArtifactsListArtifacts } from '@/generated/api/artifacts/artifacts';
import { DiffView } from '@/shared/components/DiffView';
import { useSSEStream } from '../hooks/useSSEStream';
import { StepPanel } from '../components/StepPanel';
import { getStatusColor } from '@/shared/components/StatusBadge';

const EVENT_TYPE_LABELS: Record<string, string> = {
  PipelineRunStarted: 'Started',
  PipelineRunCompleted: 'Completed',
  PipelineRunFailed: 'Failed',
  PipelineStageCompleted: 'Stage Completed',
};

export function Component() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { events, status } = useSSEStream(runId ?? null);
  const { data: artifactsResp } = useArtifactsListArtifacts(
    { run_id: runId },
    { query: { enabled: !!runId } },
  );
  const diffArtifact = ((artifactsResp?.data ?? []) as { artifact_type: string; content: string }[])
    .find((a) => a.artifact_type === 'diff' && a.content);

  // Group events by node_name (step)
  const stepMap = new Map<string, typeof events>();
  for (const evt of events) {
    const nodeName = (evt.payload as Record<string, unknown>)?.node_name as string
      ?? EVENT_TYPE_LABELS[evt.event_type] ?? evt.event_type;
    if (!stepMap.has(nodeName)) stepMap.set(nodeName, []);
    stepMap.get(nodeName)!.push(evt);
  }

  const getStepStatus = (evts: typeof events): { status: 'pending' | 'running' | 'started' | 'succeeded' | 'failed' | 'errored'; label: string } => {
    const last = evts[evts.length - 1];
    if (last?.event_type === 'PipelineRunFailed') return { status: 'failed', label: 'Failed' };
    if (last?.event_type === 'PipelineRunCompleted') return { status: 'succeeded', label: 'Completed' };
    if (last?.event_type === 'PipelineStageCompleted') return { status: 'succeeded', label: 'Stage Completed' };
    if (last?.event_type === 'PipelineRunStarted') return { status: 'started', label: 'Started' };
    return { status: 'running', label: 'Running' };
  };

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
          <Title order={2}>Run {runId?.slice(0, 8)}</Title>
          <Badge color={getStatusColor(status)}>{status}</Badge>
        </Group>
        <Group gap="sm">
          <Button
            variant="light"
            size="compact-sm"
            leftSection={<IconPlayerPlay size={14} />}
            onClick={() => navigate(`/debug?continueFrom=${runId}`)}
          >
            Re-run in Debug
          </Button>
          <Text size="sm" c="dimmed">{events.length} events</Text>
        </Group>
      </Group>

      {status === 'connecting' && (
        <Center py="xl"><Loader size="sm" /></Center>
      )}

      <Stack gap="xs">
        {Array.from(stepMap.entries()).map(([name, stepEvents]) => {
          const { status: stepStatus, label } = getStepStatus(stepEvents);
          return (
            <StepPanel
              key={name}
              stepName={name}
              status={stepStatus}
              statusLabel={label}
              events={stepEvents}
            />
          );
        })}
      </Stack>

      {diffArtifact && (
        <Paper withBorder p="md">
          <Stack gap="xs">
            <Title order={4}>Changes</Title>
            <DiffView content={diffArtifact.content} />
          </Stack>
        </Paper>
      )}

      {status === 'ended' && events.length === 0 && (
        <Paper withBorder p="md">
          <Text c="dimmed">No events recorded for this run.</Text>
        </Paper>
      )}
    </Stack>
  );
}
