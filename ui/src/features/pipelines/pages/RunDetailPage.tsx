import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center,
} from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { useSSEStream } from '../hooks/useSSEStream';
import { StepPanel } from '../components/StepPanel';

const statusColor: Record<string, string> = {
  connecting: 'gray',
  streaming: 'blue',
  ended: 'green',
  error: 'red',
};

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

  // Group events by node_name (step)
  const stepMap = new Map<string, typeof events>();
  for (const evt of events) {
    const nodeName = (evt.payload as Record<string, unknown>)?.node_name as string
      ?? EVENT_TYPE_LABELS[evt.event_type] ?? evt.event_type;
    if (!stepMap.has(nodeName)) stepMap.set(nodeName, []);
    stepMap.get(nodeName)!.push(evt);
  }

  const getStepStatus = (evts: typeof events) => {
    const last = evts[evts.length - 1];
    if (last?.event_type === 'PipelineRunFailed') return 'failed' as const;
    if (last?.event_type === 'PipelineRunCompleted') return 'succeeded' as const;
    if (last?.event_type === 'PipelineStageCompleted') return 'succeeded' as const;
    if (last?.event_type === 'PipelineRunStarted') return 'started' as const;
    return 'running' as const;
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
          <Badge color={statusColor[status] ?? 'gray'}>{status}</Badge>
        </Group>
        <Text size="sm" c="dimmed">{events.length} events</Text>
      </Group>

      {status === 'connecting' && (
        <Center py="xl"><Loader size="sm" /></Center>
      )}

      <Stack gap="xs">
        {Array.from(stepMap.entries()).map(([name, stepEvents]) => (
          <StepPanel
            key={name}
            stepName={name}
            status={getStepStatus(stepEvents)}
            events={stepEvents}
          />
        ))}
      </Stack>

      {status === 'ended' && events.length === 0 && (
        <Paper withBorder p="md">
          <Text c="dimmed">No events recorded for this run.</Text>
        </Paper>
      )}
    </Stack>
  );
}
