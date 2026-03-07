import { useState } from 'react';
import {
  Paper, Group, Text, Badge, Collapse, Stack, Code, ActionIcon,
} from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import type { StreamEvent } from '../hooks/useSSEStream';

interface StepPanelProps {
  stepName: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'errored';
  durationMs?: number;
  events: StreamEvent[];
}

const statusColor: Record<string, string> = {
  pending: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  errored: 'red',
};

export function StepPanel({ stepName, status, durationMs, events }: StepPanelProps) {
  const [opened, setOpened] = useState(status === 'failed' || status === 'errored');

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <Paper withBorder p="xs">
      <Group
        justify="space-between"
        style={{ cursor: 'pointer' }}
        onClick={() => setOpened((o) => !o)}
      >
        <Group gap="sm">
          <ActionIcon variant="subtle" size="sm">
            {opened ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          </ActionIcon>
          <Text fw={500} size="sm">{stepName}</Text>
          <Badge color={statusColor[status] ?? 'gray'} size="sm">{status}</Badge>
        </Group>
        {durationMs !== undefined && (
          <Text size="xs" c="dimmed">{formatDuration(durationMs)}</Text>
        )}
      </Group>

      <Collapse in={opened}>
        <Stack gap="xs" mt="xs" pl="md">
          {events.length === 0 ? (
            <Text size="xs" c="dimmed">No events yet</Text>
          ) : (
            events.map((evt, i) => (
              <Code key={i} block style={{ fontSize: '0.75rem' }}>
                {JSON.stringify(evt.payload ?? evt, null, 2)}
              </Code>
            ))
          )}
        </Stack>
      </Collapse>
    </Paper>
  );
}
