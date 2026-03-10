import { Box, Paper, Text, Group, Tooltip, Stack } from '@mantine/core';

interface StepTiming {
  name: string;
  stepType: string;
  durationMs: number;
  startMs: number;
}

interface StepTimingBarProps {
  steps: StepTiming[];
}

/** Color by duration: cool → warm → hot → burning */
function heatColor(ms: number): string {
  // < 10s  — cool blue/cyan
  if (ms < 10_000) return '#38bdf8';
  // < 30s  — teal
  if (ms < 30_000) return '#2dd4bf';
  // < 1m   — green
  if (ms < 60_000) return '#4ade80';
  // < 2m   — yellow-green
  if (ms < 120_000) return '#a3e635';
  // < 5m   — yellow
  if (ms < 300_000) return '#facc15';
  // < 10m  — orange
  if (ms < 600_000) return '#fb923c';
  // < 30m  — red-orange
  if (ms < 1_800_000) return '#f87171';
  // < 1h   — red
  if (ms < 3_600_000) return '#ef4444';
  // 1h+    — deep red / burning
  return '#dc2626';
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

function generateTicks(totalMs: number): number[] {
  if (totalMs <= 0) return [0];
  // Aim for 4-6 ticks
  const candidates = [
    100, 200, 500, 1000, 2000, 5000, 10_000, 15_000, 30_000,
    60_000, 120_000, 300_000, 600_000,
  ];
  const interval = candidates.find((c) => totalMs / c <= 6) ?? Math.ceil(totalMs / 5);
  const ticks: number[] = [];
  for (let t = 0; t <= totalMs; t += interval) {
    ticks.push(t);
  }
  return ticks;
}

export function StepTimingBar({ steps }: StepTimingBarProps) {
  if (steps.length === 0) return null;

  const minStart = Math.min(...steps.map((s) => s.startMs));
  const maxEnd = Math.max(...steps.map((s) => s.startMs + s.durationMs));
  const totalMs = maxEnd - minStart || 1;
  const ticks = generateTicks(totalMs);

  const LABEL_W = 120;
  const DURATION_W = 70;
  const ROW_H = 28;

  return (
    <Stack gap={0}>
      {/* Timeline header */}
      <Group gap={0} wrap="nowrap" style={{ marginBottom: 4 }}>
        <Box style={{ width: LABEL_W, flexShrink: 0 }} />
        <Box style={{ flex: 1, position: 'relative', height: 20 }}>
          {ticks.map((t) => {
            const pct = (t / totalMs) * 100;
            return (
              <Text
                key={t}
                size="xs"
                c="dimmed"
                style={{
                  position: 'absolute',
                  left: `${pct}%`,
                  transform: 'translateX(-50%)',
                  whiteSpace: 'nowrap',
                }}
              >
                {formatDuration(t)}
              </Text>
            );
          })}
        </Box>
        <Box style={{ width: DURATION_W, flexShrink: 0 }} />
      </Group>

      {/* Rows */}
      {steps.map((step, i) => {
        const offsetPct = ((step.startMs - minStart) / totalMs) * 100;
        const widthPct = Math.max((step.durationMs / totalMs) * 100, 0.5);
        const color = heatColor(step.durationMs);

        return (
          <Tooltip
            key={i}
            label={`${step.name} — started +${formatDuration(step.startMs - minStart)}, duration ${formatDuration(step.durationMs)}`}
            position="top"
          >
            <Group
              gap={0}
              wrap="nowrap"
              style={{
                height: ROW_H,
                borderBottom: '1px solid var(--mantine-color-dark-5)',
              }}
            >
              <Text
                size="xs"
                truncate
                style={{ width: LABEL_W, flexShrink: 0, paddingRight: 8 }}
              >
                {step.name}
              </Text>
              <Box
                style={{
                  flex: 1,
                  position: 'relative',
                  height: '100%',
                }}
              >
                {/* Grid lines */}
                {ticks.map((t) => (
                  <Box
                    key={t}
                    style={{
                      position: 'absolute',
                      left: `${(t / totalMs) * 100}%`,
                      top: 0,
                      bottom: 0,
                      width: 1,
                      backgroundColor: 'var(--mantine-color-dark-5)',
                    }}
                  />
                ))}
                {/* Bar */}
                <Paper
                  style={{
                    position: 'absolute',
                    left: `${offsetPct}%`,
                    width: `${widthPct}%`,
                    minWidth: 3,
                    top: 4,
                    bottom: 4,
                    backgroundColor: color,
                    borderRadius: 3,
                  }}
                />
              </Box>
              <Text
                size="xs"
                c="dimmed"
                ta="right"
                style={{ width: DURATION_W, flexShrink: 0, paddingLeft: 8 }}
              >
                {formatDuration(step.durationMs)}
              </Text>
            </Group>
          </Tooltip>
        );
      })}

      {/* Total */}
      <Text size="xs" c="dimmed" ta="right" mt={4}>
        Total wall time: {formatDuration(totalMs)}
      </Text>
    </Stack>
  );
}
