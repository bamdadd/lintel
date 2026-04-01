import { Paper, Text, Group, ThemeIcon, Stack } from '@mantine/core';
import { IconTrendingUp, IconTrendingDown, IconMinus } from '@tabler/icons-react';
import type { Icon } from '@tabler/icons-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  description?: string;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: string;
  icon: Icon;
  color: string;
}

export function MetricCard({
  label,
  value,
  description,
  trend,
  trendValue,
  icon: CardIcon,
  color,
}: MetricCardProps) {
  const TrendIcon =
    trend === 'up' ? IconTrendingUp : trend === 'down' ? IconTrendingDown : IconMinus;
  const trendColor = trend === 'up' ? 'green' : trend === 'down' ? 'red' : 'gray';

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
            {label}
          </Text>
          <Text size="xl" fw={700}>
            {value}
          </Text>
          {description && (
            <Text size="xs" c="dimmed">
              {description}
            </Text>
          )}
          {trend && trendValue && (
            <Group gap={4}>
              <TrendIcon size={14} color={`var(--mantine-color-${trendColor}-6)`} />
              <Text size="xs" c={trendColor} fw={500}>
                {trendValue}
              </Text>
            </Group>
          )}
        </Stack>
        <ThemeIcon size={40} radius="md" color={color} variant="light">
          <CardIcon size={20} />
        </ThemeIcon>
      </Group>
    </Paper>
  );
}
