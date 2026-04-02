import { useState } from 'react';
import {
  Title, Stack, Group, Paper, Text, Select, SimpleGrid, Loader, Center,
  Table, Badge, RingProgress, SegmentedControl,
} from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { usePipelinesListPipelines, usePipelinesListStages } from '@/generated/api/pipelines/pipelines';

interface PipelineRun {
  run_id: string;
  project_id: string;
  status: string;
  trigger: string;
  created_at: string;
  finished_at: string;
}

interface StageItem {
  stage_id: string;
  name: string;
  status: string;
  duration_ms?: number;
  stage_type?: string;
}

interface PipelineMetrics {
  total_runs: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  running: number;
  success_rate: number;
  avg_duration_ms: number;
  runs_over_time: Array<{
    date: string;
    succeeded: number;
    failed: number;
    cancelled: number;
    total: number;
  }>;
  failure_reasons: Array<{
    reason: string;
    count: number;
  }>;
}

function usePipelineMetrics(bucket: string) {
  return useQuery<PipelineMetrics>({
    queryKey: ['pipeline-metrics', bucket],
    queryFn: async () => {
      const resp = await fetch(`/api/v1/metrics/pipelines?bucket=${bucket}`);
      if (!resp.ok) throw new Error('Failed to fetch pipeline metrics');
      return resp.json();
    },
  });
}

export function Component() {
  const [bucket, setBucket] = useState('daily');
  const { data: metrics, isLoading: metricsLoading } = usePipelineMetrics(bucket);
  const { data: pipelinesResp } = usePipelinesListPipelines();
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const { data: stagesResp } = usePipelinesListStages(selectedRun ?? '', {
    query: { enabled: !!selectedRun },
  });

  if (metricsLoading) return <Center py="xl"><Loader /></Center>;

  const runs = (pipelinesResp?.data ?? []) as PipelineRun[];
  const stages = (stagesResp?.data ?? []) as StageItem[];

  const m = metrics ?? {
    total_runs: 0, succeeded: 0, failed: 0, cancelled: 0,
    running: 0, success_rate: 0, avg_duration_ms: 0,
    runs_over_time: [], failure_reasons: [],
  };

  // Slowest steps from selected run
  const sortedStages = [...stages]
    .filter((s) => s.duration_ms)
    .sort((a, b) => (b.duration_ms ?? 0) - (a.duration_ms ?? 0));

  const runOptions = runs.map((r) => ({
    value: r.run_id,
    label: `${r.run_id.slice(0, 8)} — ${r.status}`,
  }));

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  return (
    <Stack gap="md">
      <Title order={2}>Pipeline Metrics</Title>
      <Text c="dimmed" size="sm">
        Success rates, run history, and failure analysis across all pipelines.
      </Text>

      {/* Summary cards */}
      <SimpleGrid cols={{ base: 2, sm: 5 }}>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700}>{m.total_runs}</Text>
          <Text size="sm" c="dimmed">Total Runs</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700} c="green">{m.succeeded}</Text>
          <Text size="sm" c="dimmed">Succeeded</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700} c="red">{m.failed}</Text>
          <Text size="sm" c="dimmed">Failed</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700} c="blue">{m.running}</Text>
          <Text size="sm" c="dimmed">Running</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700}>{m.success_rate}%</Text>
          <Text size="sm" c="dimmed">Success Rate</Text>
        </Paper>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {/* Success rate gauge */}
        <Paper withBorder p="lg">
          <Text fw={500} mb="sm">Success Rate</Text>
          <Center>
            <RingProgress
              size={160}
              thickness={16}
              roundCaps
              sections={[
                { value: m.success_rate, color: 'green' },
                { value: Math.max(0, 100 - m.success_rate), color: 'red.2' },
              ]}
              label={
                <Text ta="center" fw={700} size="lg">
                  {m.success_rate}%
                </Text>
              }
            />
          </Center>
          {m.avg_duration_ms > 0 && (
            <Text size="sm" c="dimmed" ta="center" mt="sm">
              Avg duration: {formatDuration(m.avg_duration_ms)}
            </Text>
          )}
        </Paper>

        {/* Failure reasons */}
        <Paper withBorder p="lg">
          <Text fw={500} mb="sm">Failure Reasons</Text>
          {m.failure_reasons.length === 0 ? (
            <Text size="sm" c="dimmed">No failures recorded.</Text>
          ) : (
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Reason</Table.Th>
                  <Table.Th>Count</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {m.failure_reasons.slice(0, 10).map((fr) => (
                  <Table.Tr key={fr.reason}>
                    <Table.Td>
                      <Text size="sm" lineClamp={1}>{fr.reason}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color="red" variant="light">{fr.count}</Badge>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Paper>
      </SimpleGrid>

      {/* Runs over time */}
      <Paper withBorder p="lg">
        <Group justify="space-between" mb="sm">
          <Text fw={500}>Runs Over Time</Text>
          <SegmentedControl
            size="xs"
            value={bucket}
            onChange={setBucket}
            data={[
              { label: 'Daily', value: 'daily' },
              { label: 'Weekly', value: 'weekly' },
            ]}
          />
        </Group>
        {m.runs_over_time.length === 0 ? (
          <Text size="sm" c="dimmed">No time-series data available yet.</Text>
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Date</Table.Th>
                <Table.Th>Total</Table.Th>
                <Table.Th>Succeeded</Table.Th>
                <Table.Th>Failed</Table.Th>
                <Table.Th>Cancelled</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {m.runs_over_time.map((row) => (
                <Table.Tr key={row.date}>
                  <Table.Td><Text size="sm" ff="monospace">{row.date}</Text></Table.Td>
                  <Table.Td>{row.total}</Table.Td>
                  <Table.Td><Text c="green">{row.succeeded}</Text></Table.Td>
                  <Table.Td><Text c="red">{row.failed}</Text></Table.Td>
                  <Table.Td>{row.cancelled}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Step breakdown for selected run */}
      <Group>
        <Select
          label="Select run for step breakdown"
          placeholder="Choose a pipeline run"
          data={runOptions}
          value={selectedRun}
          onChange={setSelectedRun}
          searchable
          clearable
          w={300}
        />
      </Group>

      {selectedRun && sortedStages.length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Slowest Steps</Text>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Step</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Duration</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sortedStages.slice(0, 10).map((s) => (
                <Table.Tr key={s.stage_id}>
                  <Table.Td>{s.name}</Table.Td>
                  <Table.Td><Badge variant="light" size="sm">{s.stage_type ?? 'step'}</Badge></Table.Td>
                  <Table.Td><Text size="sm" ff="monospace">{formatDuration(s.duration_ms ?? 0)}</Text></Table.Td>
                  <Table.Td>
                    <Badge
                      color={s.status === 'succeeded' ? 'green' : s.status === 'failed' ? 'red' : 'gray'}
                      size="sm"
                    >
                      {s.status}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  );
}
