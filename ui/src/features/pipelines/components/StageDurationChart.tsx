import { Box, Group, Paper, Stack, Text, Tooltip } from '@mantine/core';
import type { StageItem } from './StageCard';

interface StageDurationChartProps {
  stages: StageItem[];
}

function statusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'var(--mantine-color-green-6)';
    case 'failed':
    case 'error':
      return 'var(--mantine-color-red-6)';
    case 'running':
      return 'var(--mantine-color-yellow-5)';
    case 'cancelled':
      return 'var(--mantine-color-gray-5)';
    default:
      return 'var(--mantine-color-blue-4)';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed':
      return 'Completed';
    case 'failed':
    case 'error':
      return 'Failed';
    case 'running':
      return 'Running';
    case 'cancelled':
      return 'Cancelled';
    case 'pending':
      return 'Pending';
    default:
      return status;
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

const LABEL_W = 120;
const DURATION_W = 70;
const ROW_H = 32;

export function StageDurationChart({ stages }: StageDurationChartProps) {
  const stagesWithDuration = stages.filter(
    (s) => s.duration_ms != null && s.duration_ms > 0,
  );

  if (stagesWithDuration.length === 0) {
    return (
      <Paper withBorder p="md">
        <Text c="dimmed">No duration data available yet</Text>
      </Paper>
    );
  }

  const maxDuration = Math.max(...stagesWithDuration.map((s) => s.duration_ms ?? 0));
  const totalDuration = stagesWithDuration.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);

  return (
    <Stack gap={0}>
      {/* Legend */}
      <Group gap="md" mb="xs">
        {[
          { status: 'completed', label: 'Completed' },
          { status: 'failed', label: 'Failed' },
          { status: 'running', label: 'Running' },
        ].map(({ status, label }) => (
          <Group key={status} gap={4}>
            <Box
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: statusColor(status),
              }}
            />
            <Text size="xs" c="dimmed">{label}</Text>
          </Group>
        ))}
      </Group>

      {/* Bars */}
      {stagesWithDuration.map((stage) => {
        const widthPct = Math.max(((stage.duration_ms ?? 0) / maxDuration) * 100, 2);
        const color = statusColor(stage.status);

        return (
          <Tooltip
            key={stage.stage_id}
            label={`${stage.name} — ${statusLabel(stage.status)} — ${formatDuration(stage.duration_ms ?? 0)}`}
            position="top"
          >
            <Group
              gap={0}
              wrap="nowrap"
              style={{
                height: ROW_H,
                borderBottom: '1px solid var(--mantine-color-default-border)',
              }}
            >
              <Text
                size="xs"
                truncate
                fw={500}
                style={{ width: LABEL_W, flexShrink: 0, paddingRight: 8 }}
              >
                {stage.name}
              </Text>
              <Box style={{ flex: 1, position: 'relative', height: '100%' }}>
                <Paper
                  style={{
                    position: 'absolute',
                    left: 0,
                    width: `${widthPct}%`,
                    minWidth: 4,
                    top: 5,
                    bottom: 5,
                    backgroundColor: color,
                    borderRadius: 4,
                    transition: 'width 0.3s ease',
                  }}
                />
              </Box>
              <Text
                size="xs"
                c="dimmed"
                ta="right"
                style={{ width: DURATION_W, flexShrink: 0, paddingLeft: 8 }}
              >
                {formatDuration(stage.duration_ms ?? 0)}
              </Text>
            </Group>
          </Tooltip>
        );
      })}

      {/* Total */}
      <Text size="xs" c="dimmed" ta="right" mt={4}>
        Total: {formatDuration(totalDuration)}
      </Text>
    </Stack>
  );
}
