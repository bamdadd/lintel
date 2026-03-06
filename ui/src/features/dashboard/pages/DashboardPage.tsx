import { SimpleGrid, Title, Stack, Text, Table, Loader, Center } from '@mantine/core';
import { useMetricsOverviewMetrics } from '@/generated/api/metrics/metrics';
import { useThreadsListThreads } from '@/generated/api/threads/threads';
import { useEventsListEvents } from '@/generated/api/events/events';
import { StatsCard } from '../components/StatsCard';
import { StatusBadge } from '@/shared/components/StatusBadge';

interface OverviewData {
  pii?: { total_detected?: number; total_anonymised?: number };
  sandboxes?: { total?: number };
  connections?: { total?: number };
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
