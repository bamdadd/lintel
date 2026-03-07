import { useState } from 'react';
import {
  ActionIcon,
  SimpleGrid,
  Title,
  Stack,
  Text,
  Table,
  Loader,
  Center,
  Paper,
  Group,
  Button,
  ThemeIcon,
  List,
} from '@mantine/core';
import {
  IconRocket,
  IconCheck,
  IconCircleDashed,
  IconX,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useMetricsOverviewMetrics } from '@/generated/api/metrics/metrics';
import { useThreadsListThreads } from '@/generated/api/threads/threads';
import { useEventsListEvents } from '@/generated/api/events/events';
import { StatsCard } from '../components/StatsCard';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { customInstance } from '@/shared/api/client';

interface OverviewData {
  pii?: { total_detected?: number; total_anonymised?: number };
  sandboxes?: { total?: number };
  connections?: { total?: number };
}

interface OnboardingStatus {
  has_ai_provider: boolean;
  has_repo: boolean;
  has_chat: boolean;
  is_complete: boolean;
}

function useOnboardingStatus() {
  return useQuery({
    queryKey: ['/api/v1/onboarding/status'],
    queryFn: () =>
      customInstance<{ data: OnboardingStatus; status: number }>(
        '/api/v1/onboarding/status',
        { method: 'GET' },
      ).then((r) => r.data),
  });
}

function OnboardingBanner() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useOnboardingStatus();
  const [dismissed, setDismissed] = useState(false);

  if (isLoading || !status || dismissed) return null;

  const steps = [
    { label: 'AI provider configured', done: status.has_ai_provider },
    { label: 'Repository connected', done: status.has_repo },
    { label: 'Chat enabled (optional)', done: status.has_chat },
  ];

  return (
    <Paper withBorder p="lg" radius="md">
      <Group justify="space-between" align="flex-start">
        <Group align="flex-start" gap="md">
          <ThemeIcon
            size={48}
            radius="xl"
            color={status.is_complete ? 'green' : 'blue'}
            variant="light"
          >
            {status.is_complete ? <IconCheck size={24} /> : <IconRocket size={24} />}
          </ThemeIcon>
          <Stack gap="xs">
            <Title order={4}>
              {status.is_complete ? 'Workspace ready' : 'Get started with Lintel'}
            </Title>
            <Text c="dimmed" size="sm">
              {status.is_complete
                ? 'Your workspace is fully configured.'
                : 'Complete setup to start running AI workflows on your codebase.'}
            </Text>
            <List spacing={4} size="sm" mt={4}>
              {steps.map((s) => (
                <List.Item
                  key={s.label}
                  icon={
                    s.done ? (
                      <ThemeIcon color="green" size={20} radius="xl">
                        <IconCheck size={12} />
                      </ThemeIcon>
                    ) : (
                      <ThemeIcon color="gray" size={20} radius="xl" variant="light">
                        <IconCircleDashed size={12} />
                      </ThemeIcon>
                    )
                  }
                >
                  <Text size="sm" c={s.done ? 'dimmed' : undefined}>
                    {s.label}
                  </Text>
                </List.Item>
              ))}
            </List>
          </Stack>
        </Group>
        <Group gap="sm">
          {!status.is_complete && (
            <Button onClick={() => void navigate('/setup')}>
              Set up workspace
            </Button>
          )}
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={() => setDismissed(true)}
            aria-label="Dismiss onboarding banner"
          >
            <IconX size={16} />
          </ActionIcon>
        </Group>
      </Group>
    </Paper>
  );
}

export function Component() {
  const { data: overviewResp } = useMetricsOverviewMetrics();
  const { data: threadsResp, isLoading: threadsLoading } = useThreadsListThreads();
  const { data: eventsResp, isLoading: eventsLoading } = useEventsListEvents();

  const overview = overviewResp?.data as OverviewData | undefined;
  const threads = threadsResp?.data;
  const events = eventsResp?.data;

  return (
    <Stack gap="lg">
      <Title order={2}>Dashboard</Title>

      <OnboardingBanner />

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatsCard label="Sandboxes" value={overview?.sandboxes?.total ?? 0} />
        <StatsCard label="Connections" value={overview?.connections?.total ?? 0} />
        <StatsCard label="PII Detected" value={overview?.pii?.total_detected ?? 0} />
        <StatsCard label="PII Anonymised" value={overview?.pii?.total_anonymised ?? 0} />
      </SimpleGrid>

      <Title order={3}>Recent Threads</Title>
      {threadsLoading ? (
        <Center><Loader size="sm" /></Center>
      ) : threads && threads.length > 0 ? (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Stream ID</Table.Th>
              <Table.Th>Phase</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {threads.slice(0, 10).map((t, i) => (
              <Table.Tr key={i}>
                <Table.Td>{String(t.stream_id ?? '')}</Table.Td>
                <Table.Td>{String(t.phase ?? '')}</Table.Td>
                <Table.Td>
                  <StatusBadge status={String(t.status ?? 'unknown')} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : (
        <Text c="dimmed">No threads yet.</Text>
      )}

      <Title order={3}>Recent Events</Title>
      {eventsLoading ? (
        <Center><Loader size="sm" /></Center>
      ) : events && events.length > 0 ? (
        <Text c="dimmed">{events.length} events in backlog</Text>
      ) : (
        <Text c="dimmed">No events yet.</Text>
      )}
    </Stack>
  );
}
