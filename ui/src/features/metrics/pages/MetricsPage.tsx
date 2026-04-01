import { Stack, Title, Text, SimpleGrid, Paper, Loader, Center } from '@mantine/core';
import { IconUsers, IconUserCheck } from '@tabler/icons-react';
import { useMetricsOverviewMetrics } from '@/generated/api/metrics/metrics';
import { useMetricsAgentMetrics } from '@/generated/api/metrics/metrics';
import { DORAMetrics } from '../components/DORAMetrics';
import { AgentMetrics } from '../components/AgentMetrics';
import { MetricCard } from '../components/MetricCard';

interface OverviewData {
  dora?: {
    deployment_frequency?: number;
    lead_time_hours?: number;
    change_failure_rate?: number;
    mttr_hours?: number;
  };
  human?: {
    total_reviews?: number;
    avg_review_time_hours?: number;
    approval_rate?: number;
    interventions?: number;
  };
  team?: {
    active_members?: number;
    workflows_per_member?: number;
    collaboration_score?: number;
    throughput?: number;
  };
  counts?: {
    agent_steps?: number;
  };
}

interface AgentData {
  total_steps?: number;
  accuracy?: number;
  rework_rate?: number;
  token_efficiency?: number;
  avg_tokens_per_step?: number;
}

export function Component() {
  const { data: overviewResp, isLoading: overviewLoading } = useMetricsOverviewMetrics();
  const { data: agentResp, isLoading: agentLoading } = useMetricsAgentMetrics();

  const overview = overviewResp?.data as OverviewData | undefined;
  const agentData = agentResp?.data as AgentData | undefined;

  if (overviewLoading || agentLoading) {
    return (
      <Center py="xl">
        <Loader size="lg" />
      </Center>
    );
  }

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Metrics Dashboard</Title>
        <Text c="dimmed" size="sm" mt={4}>
          DORA, agent, human, and team performance metrics across your workspace.
        </Text>
      </div>

      {/* DORA Metrics */}
      <DORAMetrics data={overview?.dora} />

      {/* Agent Metrics */}
      <AgentMetrics data={agentData} />

      {/* Human & Team Metrics */}
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {/* Human Metrics */}
        <Paper withBorder p="lg" radius="md">
          <Title order={4} mb="md">
            Human Metrics
          </Title>
          {!overview?.human ? (
            <Text c="dimmed" size="sm">
              No human review metrics available yet.
            </Text>
          ) : (
            <Stack gap="sm">
              <MetricCard
                label="Total Reviews"
                value={overview.human.total_reviews ?? 0}
                icon={IconUserCheck}
                color="teal"
              />
              <MetricCard
                label="Avg Review Time"
                value={
                  overview.human.avg_review_time_hours !== undefined
                    ? `${overview.human.avg_review_time_hours.toFixed(1)}h`
                    : '--'
                }
                icon={IconUserCheck}
                color="blue"
              />
              <MetricCard
                label="Approval Rate"
                value={
                  overview.human.approval_rate !== undefined
                    ? `${(overview.human.approval_rate * 100).toFixed(1)}%`
                    : '--'
                }
                icon={IconUserCheck}
                color="green"
              />
            </Stack>
          )}
        </Paper>

        {/* Team Metrics */}
        <Paper withBorder p="lg" radius="md">
          <Title order={4} mb="md">
            Team Metrics
          </Title>
          {!overview?.team ? (
            <Text c="dimmed" size="sm">
              No team metrics available yet.
            </Text>
          ) : (
            <Stack gap="sm">
              <MetricCard
                label="Active Members"
                value={overview.team.active_members ?? 0}
                icon={IconUsers}
                color="indigo"
              />
              <MetricCard
                label="Workflows / Member"
                value={overview.team.workflows_per_member?.toFixed(1) ?? '--'}
                icon={IconUsers}
                color="violet"
              />
              <MetricCard
                label="Throughput"
                value={overview.team.throughput ?? 0}
                description="Completed items per week"
                icon={IconUsers}
                color="cyan"
              />
            </Stack>
          )}
        </Paper>
      </SimpleGrid>
    </Stack>
  );
}
