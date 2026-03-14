import { Paper, Text } from '@mantine/core';
import { BarChart } from '@mantine/charts';

interface RunTimelineProps {
  runs: Array<{
    status: string;
    created_at: string;
  }>;
}

function getLast7Days(): string[] {
  const days: string[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toLocaleDateString('en-US', { weekday: 'short' }));
  }
  return days;
}

function bucketRuns(runs: RunTimelineProps['runs']): Array<{ day: string; passed: number; failed: number }> {
  const days = getLast7Days();
  const now = new Date();
  const buckets: Record<string, { passed: number; failed: number }> = {};
  for (const day of days) {
    buckets[day] = { passed: 0, failed: 0 };
  }

  for (const run of runs) {
    const runDate = new Date(run.created_at);
    const diffDays = Math.floor((now.getTime() - runDate.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays >= 0 && diffDays < 7) {
      const dayLabel = runDate.toLocaleDateString('en-US', { weekday: 'short' });
      if (buckets[dayLabel]) {
        if (run.status === 'completed' || run.status === 'succeeded') {
          buckets[dayLabel].passed++;
        } else if (run.status === 'failed') {
          buckets[dayLabel].failed++;
        }
      }
    }
  }

  return days.map((day) => ({ day, passed: buckets[day]?.passed ?? 0, failed: buckets[day]?.failed ?? 0 }));
}

export function RunTimeline({ runs }: RunTimelineProps) {
  const data = bucketRuns(runs);
  const hasData = data.some((d) => d.passed > 0 || d.failed > 0);

  if (!hasData) {
    return (
      <Paper p="md" radius="md" withBorder>
        <Text size="sm" fw={500} mb="xs">Run Timeline (7 days)</Text>
        <Text size="xs" c="dimmed">No runs in the last 7 days</Text>
      </Paper>
    );
  }

  return (
    <Paper p="md" radius="md" withBorder>
      <Text size="sm" fw={500} mb="xs">Run Timeline (7 days)</Text>
      <BarChart
        h={120}
        data={data}
        dataKey="day"
        type="stacked"
        series={[
          { name: 'passed', color: 'green' },
          { name: 'failed', color: 'red' },
        ]}
        withTooltip
        withLegend={false}
      />
    </Paper>
  );
}
