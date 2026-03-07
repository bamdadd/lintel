import { useState } from 'react';
import {
  Title, Stack, Group, Paper, Text, Select, SimpleGrid, Loader, Center,
  Table, Badge,
} from '@mantine/core';
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

export function Component() {
  const { data: pipelinesResp, isLoading } = usePipelinesListPipelines();
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const { data: stagesResp } = usePipelinesListStages(selectedRun ?? '', {
    query: { enabled: !!selectedRun },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const runs = (pipelinesResp?.data ?? []) as PipelineRun[];
  const stages = (stagesResp?.data ?? []) as StageItem[];

  // Compute metrics
  const totalRuns = runs.length;
  const succeededRuns = runs.filter((r) => r.status === 'succeeded').length;
  const failedRuns = runs.filter((r) => r.status === 'failed').length;
  const successRate = totalRuns > 0 ? ((succeededRuns / totalRuns) * 100).toFixed(1) : '0';

  // Slowest steps from selected run
  const sortedStages = [...stages]
    .filter((s) => s.duration_ms)
    .sort((a, b) => (b.duration_ms ?? 0) - (a.duration_ms ?? 0));

  const runOptions = runs.map((r) => ({
    value: r.run_id,
    label: `${r.run_id.slice(0, 8)} — ${r.status}`,
  }));

  return (
    <Stack gap="md">
      <Title order={2}>Pipeline Metrics</Title>

      <SimpleGrid cols={4}>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700}>{totalRuns}</Text>
          <Text size="sm" c="dimmed">Total Runs</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700} c="green">{succeededRuns}</Text>
          <Text size="sm" c="dimmed">Succeeded</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700} c="red">{failedRuns}</Text>
          <Text size="sm" c="dimmed">Failed</Text>
        </Paper>
        <Paper withBorder p="md" ta="center">
          <Text size="xl" fw={700}>{successRate}%</Text>
          <Text size="sm" c="dimmed">Success Rate</Text>
        </Paper>
      </SimpleGrid>

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
                  <Table.Td><Text size="sm" ff="monospace">{s.duration_ms}ms</Text></Table.Td>
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

      {runs.length > 0 && (
        <Paper withBorder p="md">
          <Text fw={500} mb="sm">Active Runs</Text>
          {runs.filter((r) => r.status === 'running').length === 0 ? (
            <Text size="sm" c="dimmed">No active runs</Text>
          ) : (
            <Stack gap="xs">
              {runs
                .filter((r) => r.status === 'running')
                .map((r) => (
                  <Group key={r.run_id} gap="sm">
                    <Text size="sm" ff="monospace">{r.run_id.slice(0, 8)}</Text>
                    <Badge color="blue" size="sm">running</Badge>
                    <Text size="xs" c="dimmed">
                      Started: {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                    </Text>
                  </Group>
                ))}
            </Stack>
          )}
        </Paper>
      )}
    </Stack>
  );
}
