import { SimpleGrid, Paper, Text, Group, Badge } from '@mantine/core';
import type { FlowMetrics } from '../types';
import { FLOW_TYPE_LABELS, FLOW_TYPE_COLORS } from '../types';

interface FlowMetricsSummaryProps {
  metrics: FlowMetrics;
}

export function FlowMetricsSummary({ metrics }: FlowMetricsSummaryProps) {
  return (
    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
      <Paper p="md" withBorder>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Total Flows
        </Text>
        <Text size="xl" fw={700} mt={4}>
          {metrics.total_flows}
        </Text>
      </Paper>
      <Paper p="md" withBorder>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Avg Depth
        </Text>
        <Text size="xl" fw={700} mt={4}>
          {metrics.avg_depth.toFixed(1)}
        </Text>
      </Paper>
      <Paper p="md" withBorder>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Max Depth
        </Text>
        <Text size="xl" fw={700} mt={4}>
          {metrics.max_depth}
        </Text>
      </Paper>
      <Paper p="md" withBorder>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Complexity
        </Text>
        <Text size="xl" fw={700} mt={4}>
          {metrics.complexity_score.toFixed(1)}
        </Text>
      </Paper>
      {Object.keys(metrics.flows_by_type).length > 0 && (
        <Paper p="md" withBorder style={{ gridColumn: '1 / -1' }}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb="xs">
            Flows by Type
          </Text>
          <Group gap="xs">
            {Object.entries(metrics.flows_by_type).map(([type, count]) => (
              <Badge
                key={type}
                color={FLOW_TYPE_COLORS[type] ?? 'gray'}
                variant="light"
                size="lg"
              >
                {FLOW_TYPE_LABELS[type] ?? type}: {count}
              </Badge>
            ))}
          </Group>
        </Paper>
      )}
    </SimpleGrid>
  );
}
