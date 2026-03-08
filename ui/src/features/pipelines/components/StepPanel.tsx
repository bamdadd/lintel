import { useState } from 'react';
import {
  Paper, Group, Text, Badge, Collapse, Stack, Code, ActionIcon,
} from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import type { StreamEvent } from '../hooks/useSSEStream';

interface StepPanelProps {
  stepName: string;
  status: 'pending' | 'running' | 'started' | 'succeeded' | 'failed' | 'errored';
  statusLabel?: string;
  durationMs?: number;
  events: StreamEvent[];
}

const statusColor: Record<string, string> = {
  pending: 'gray',
  started: 'teal',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  errored: 'red',
};

export function StepPanel({ stepName, status, statusLabel, durationMs, events }: StepPanelProps) {
  const [opened, setOpened] = useState(status === 'failed' || status === 'errored');

  // Extract token usage from stage output events
  const tokenUsage = (() => {
    for (const evt of events) {
      const output = (evt.payload as Record<string, unknown>)?.output as Record<string, unknown> | undefined;
      const usage = output?.token_usage as { input_tokens: number; output_tokens: number; total_tokens: number } | undefined;
      if (usage?.total_tokens) return usage;
    }
    return null;
  })();

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
          <Badge color={statusColor[status] ?? 'gray'} size="sm">{statusLabel ?? status}</Badge>
        </Group>
        <Group gap="sm">
          {tokenUsage && (
            <Text size="xs" c="dimmed">
              {tokenUsage.total_tokens.toLocaleString()} tokens
            </Text>
          )}
          {durationMs !== undefined && (
            <Text size="xs" c="dimmed">{formatDuration(durationMs)}</Text>
          )}
        </Group>
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
