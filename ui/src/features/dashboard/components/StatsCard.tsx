import { Paper, Text, Title } from '@mantine/core';

interface StatsCardProps {
  label: string;
  value: number | string;
}

export function StatsCard({ label, value }: StatsCardProps) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
        {label}
      </Text>
      <Title order={3} mt={4}>
        {value}
      </Title>
    </Paper>
  );
}
