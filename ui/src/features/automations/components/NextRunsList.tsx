import { Stack, Text } from '@mantine/core';
import { CronExpressionParser } from 'cron-parser';

interface NextRunsListProps {
  schedule: string;
  timezone?: string;
  count?: number;
}

export function NextRunsList({ schedule, timezone = 'UTC', count = 5 }: NextRunsListProps) {
  const dates: Date[] = [];
  try {
    const cron = CronExpressionParser.parse(schedule, { tz: timezone });
    for (let i = 0; i < count; i++) {
      dates.push(cron.next().toDate());
    }
  } catch {
    return <Text size="xs" c="red">Invalid cron expression</Text>;
  }

  return (
    <Stack gap={4}>
      {dates.map((d, i) => (
        <Text key={i} size="xs" ff="monospace" c={i < 2 ? undefined : 'dimmed'}>
          {d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC')}
        </Text>
      ))}
    </Stack>
  );
}
