import { SimpleGrid, Text, Paper, Title, Group, Badge } from '@mantine/core';
import {
  IconRocket,
  IconClock,
  IconBug,
  IconHeartbeat,
} from '@tabler/icons-react';
import { MetricCard } from './MetricCard';

interface DORAData {
  deployment_frequency?: number;
  lead_time_hours?: number;
  change_failure_rate?: number;
  mttr_hours?: number;
}

interface DORAMetricsProps {
  data?: DORAData;
}

function rateLabel(cfr?: number): string {
  if (cfr === undefined) return '--';
  return `${(cfr * 100).toFixed(1)}%`;
}

function hoursLabel(hours?: number): string {
  if (hours === undefined) return '--';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

function doraLevel(data?: DORAData): { label: string; color: string } {
  if (!data) return { label: 'No data', color: 'gray' };
  if (
    (data.deployment_frequency ?? 0) >= 1 &&
    (data.lead_time_hours ?? 999) < 24 &&
    (data.change_failure_rate ?? 1) < 0.15 &&
    (data.mttr_hours ?? 999) < 1
  ) {
    return { label: 'Elite', color: 'green' };
  }
  if (
    (data.deployment_frequency ?? 0) >= 0.14 &&
    (data.lead_time_hours ?? 999) < 168
  ) {
    return { label: 'High', color: 'blue' };
  }
  if ((data.deployment_frequency ?? 0) >= 0.033) {
    return { label: 'Medium', color: 'yellow' };
  }
  return { label: 'Low', color: 'orange' };
}

export function DORAMetrics({ data }: DORAMetricsProps) {
  const level = doraLevel(data);

  return (
    <Paper withBorder p="lg" radius="md">
      <Group justify="space-between" mb="md">
        <Title order={4}>DORA Metrics</Title>
        <Badge color={level.color} variant="light" size="lg">
          {level.label}
        </Badge>
      </Group>
      {!data ? (
        <Text c="dimmed" size="sm">
          No DORA metrics available yet. Run pipelines to generate data.
        </Text>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <MetricCard
            label="Deploy Frequency"
            value={data.deployment_frequency?.toFixed(2) ?? '--'}
            description="Deploys per day"
            icon={IconRocket}
            color="blue"
          />
          <MetricCard
            label="Lead Time"
            value={hoursLabel(data.lead_time_hours)}
            description="Commit to deploy"
            icon={IconClock}
            color="violet"
          />
          <MetricCard
            label="Change Failure Rate"
            value={rateLabel(data.change_failure_rate)}
            description="% of deploys causing failure"
            icon={IconBug}
            color="orange"
          />
          <MetricCard
            label="MTTR"
            value={hoursLabel(data.mttr_hours)}
            description="Mean time to recover"
            icon={IconHeartbeat}
            color="red"
          />
        </SimpleGrid>
      )}
    </Paper>
  );
}
