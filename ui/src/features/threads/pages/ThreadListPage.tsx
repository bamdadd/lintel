import { Title, Table, Loader, Center, Stack } from '@mantine/core';
import { useNavigate } from 'react-router';
import { useThreadsListThreads } from '@/generated/api/threads/threads';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EmptyState } from '@/shared/components/EmptyState';

export function Component() {
  const { data: resp, isLoading } = useThreadsListThreads();
  const navigate = useNavigate();
  const threads = resp?.data;

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Title order={2}>Threads</Title>
      {!threads || threads.length === 0 ? (
        <EmptyState
          title="No threads yet"
          description="Threads appear when workflows are triggered from Slack."
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Stream ID</Table.Th>
              <Table.Th>Channel</Table.Th>
              <Table.Th>Phase</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {threads.map((t, i) => (
              <Table.Tr
                key={i}
                style={{ cursor: 'pointer' }}
                onClick={() => void navigate(`/threads/${String(t.stream_id ?? '')}`)}
              >
                <Table.Td>{String(t.stream_id ?? '')}</Table.Td>
                <Table.Td>{String(t.channel_id ?? '')}</Table.Td>
                <Table.Td>{String(t.phase ?? '')}</Table.Td>
                <Table.Td>
                  <StatusBadge status={String(t.status ?? 'unknown')} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
