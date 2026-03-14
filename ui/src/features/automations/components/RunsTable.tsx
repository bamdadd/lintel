import { Group, Paper, Stack, Table, Text, UnstyledButton } from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';

import { StatusBadge } from '@/shared/components/StatusBadge';

interface PipelineRun {
  run_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  stages?: Array<{
    name: string;
    status: string;
    duration_ms?: number;
  }>;
}

interface RunsTableProps {
  runs: PipelineRun[];
}

function formatDuration(startStr: string, endStr?: string): string {
  if (!endStr) return '\u2014';
  const start = new Date(startStr).getTime();
  const end = new Date(endStr).getTime();
  const seconds = Math.floor((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m ${secs}s`;
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <Table.Tr
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <Table.Td w={30}>
          {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </Table.Td>
        <Table.Td>
          <Text size="xs" ff="monospace">{run.run_id.slice(0, 12)}</Text>
        </Table.Td>
        <Table.Td><StatusBadge status={run.status} /></Table.Td>
        <Table.Td><Text size="xs">{formatTimeAgo(run.created_at)}</Text></Table.Td>
        <Table.Td><Text size="xs">{formatDuration(run.created_at, run.completed_at)}</Text></Table.Td>
      </Table.Tr>
      {expanded && (
        <Table.Tr>
          <Table.Td colSpan={5} style={{ background: 'var(--mantine-color-dark-7)' }}>
            <Stack gap="xs" p="xs">
              <Text size="xs" c="dimmed">Pipeline Stages</Text>
              <Group gap="xs">
                {(run.stages ?? []).map((stage) => (
                  <Paper key={stage.name} p="xs" radius="sm" withBorder style={{ flex: 1 }}>
                    <Text size="xs" c="dimmed">{stage.name}</Text>
                    <StatusBadge status={stage.status} />
                    {stage.duration_ms != null && (
                      <Text size="xs" c="dimmed" mt={2}>
                        {Math.round(stage.duration_ms / 1000)}s
                      </Text>
                    )}
                  </Paper>
                ))}
              </Group>
              <Group justify="flex-end">
                <UnstyledButton onClick={() => navigate(`/pipelines/${run.run_id}`)}>
                  <Text size="xs" c="blue">View full pipeline &rarr;</Text>
                </UnstyledButton>
              </Group>
            </Stack>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

export function RunsTable({ runs }: RunsTableProps) {
  if (runs.length === 0) {
    return <Text size="sm" c="dimmed">No runs yet</Text>;
  }

  return (
    <Table highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={30} />
          <Table.Th>Run ID</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>Started</Table.Th>
          <Table.Th>Duration</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {runs.map((run) => (
          <RunRow key={run.run_id} run={run} />
        ))}
      </Table.Tbody>
    </Table>
  );
}
