import { Paper, Text, Group, Tooltip, Stack } from '@mantine/core';

interface StepTiming {
  name: string;
  stepType: string;
  durationMs: number;
  startMs: number;
}

interface StepTimingBarProps {
  steps: StepTiming[];
}

const typeColors: Record<string, string> = {
  agent: '#3b82f6',
  tool: '#6b7280',
  approval: '#eab308',
};

export function StepTimingBar({ steps }: StepTimingBarProps) {
  if (steps.length === 0) return null;

  const maxDuration = Math.max(...steps.map((s) => s.durationMs), 1);
  const totalDuration = steps.reduce((sum, s) => sum + s.durationMs, 0);

  return (
    <Stack gap="xs">
      {steps.map((step, i) => {
        const widthPct = Math.max((step.durationMs / maxDuration) * 100, 2);
        const color = typeColors[step.stepType] ?? '#6b7280';

        return (
          <Tooltip
            key={i}
            label={`${step.name}: ${step.durationMs}ms`}
            position="right"
          >
            <Group gap="xs" wrap="nowrap">
              <Text size="xs" w={120} truncate>{step.name}</Text>
              <Paper
                style={{
                  width: `${widthPct}%`,
                  minWidth: 4,
                  height: 20,
                  backgroundColor: color,
                  borderRadius: 4,
                }}
              />
              <Text size="xs" c="dimmed">{step.durationMs}ms</Text>
            </Group>
          </Tooltip>
        );
      })}
      <Text size="xs" c="dimmed" ta="right">
        Total: {totalDuration}ms
      </Text>
    </Stack>
  );
}
