import {
  Title, Stack, Table, Loader, Center, Badge, Text, TextInput, Group,
} from '@mantine/core';
import { useState } from 'react';
import { useAuditListAuditEntries } from '@/generated/api/audit/audit';
import { EmptyState } from '@/shared/components/EmptyState';

interface AuditEntry {
  entry_id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export function Component() {
  const { data: resp, isLoading } = useAuditListAuditEntries();
  const [filter, setFilter] = useState('');

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const entries = (resp?.data ?? []) as AuditEntry[];
  const filtered = entries.filter((e) =>
    e.actor?.toLowerCase().includes(filter.toLowerCase())
    || e.action?.toLowerCase().includes(filter.toLowerCase())
    || e.resource_type?.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Audit Log</Title>
        <TextInput placeholder="Filter by actor, action, or resource..." value={filter} onChange={(e) => setFilter(e.currentTarget.value)} style={{ width: 300 }} />
      </Group>

      {entries.length === 0 ? (
        <EmptyState title="No audit entries" description="Audit events will appear here as actions are performed" />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Timestamp</Table.Th>
              <Table.Th>Actor</Table.Th>
              <Table.Th>Action</Table.Th>
              <Table.Th>Resource</Table.Th>
              <Table.Th>Details</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filtered.map((e) => (
              <Table.Tr key={e.entry_id}>
                <Table.Td><Text size="sm">{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</Text></Table.Td>
                <Table.Td>{e.actor}</Table.Td>
                <Table.Td><Badge variant="light">{e.action}</Badge></Table.Td>
                <Table.Td>
                  <Text size="sm">{e.resource_type} <Text span c="dimmed" size="xs">{e.resource_id}</Text></Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed" lineClamp={1}>{e.details ? JSON.stringify(e.details) : '—'}</Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
