import { SimpleGrid, Text, Paper, Title } from '@mantine/core';
import { IconRobot, IconRefresh, IconCoin, IconTarget } from '@tabler/icons-react';
import { MetricCard } from './MetricCard';

interface AgentData {
  total_steps?: number;
  accuracy?: number;
  rework_rate?: number;
  token_efficiency?: number;
  avg_tokens_per_step?: number;
}

interface AgentMetricsProps {
  data?: AgentData;
}

export function AgentMetrics({ data }: AgentMetricsProps) {
  return (
    <Paper withBorder p="lg" radius="md">
      <Title order={4} mb="md">
        Agent Metrics
      </Title>
      {!data ? (
        <Text c="dimmed" size="sm">
          No agent metrics available yet. Run agent workflows to generate data.
        </Text>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <MetricCard
            label="Total Steps"
            value={data.total_steps ?? 0}
            icon={IconRobot}
            color="grape"
          />
          <MetricCard
            label="Accuracy"
            value={data.accuracy !== undefined ? `${(data.accuracy * 100).toFixed(1)}%` : '--'}
            icon={IconTarget}
            color="green"
          />
          <MetricCard
            label="Rework Rate"
            value={
              data.rework_rate !== undefined ? `${(data.rework_rate * 100).toFixed(1)}%` : '--'
            }
            description="Steps requiring revision"
            icon={IconRefresh}
            color="orange"
          />
          <MetricCard
            label="Token Efficiency"
            value={data.avg_tokens_per_step?.toLocaleString() ?? '--'}
            description="Avg tokens per step"
            icon={IconCoin}
            color="cyan"
          />
        </SimpleGrid>
      )}
    </Paper>
  );
}
