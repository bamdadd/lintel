import { useState } from 'react';
import {
  Title, Stack, Table, Loader, Center, Badge, Text, TextInput, Group,
  Collapse, Paper, ActionIcon,
} from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useAuditListAuditEntries } from '@/generated/api/audit/audit';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';

interface AuditEntry {
  entry_id: string;
  actor: string;
  actor_type?: string;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string;
  details: Record<string, unknown>;
}

const actionColor: Record<string, string> = {
  create: 'green',
  created: 'green',
  update: 'blue',
  updated: 'blue',
  delete: 'red',
  deleted: 'red',
  remove: 'red',
  removed: 'red',
  approve: 'teal',
  approved: 'teal',
  reject: 'orange',
  rejected: 'orange',
};

/** Get a badge color based on action keyword */
function getActionColor(action: string): string {
  const lower = action.toLowerCase();
  for (const [key, color] of Object.entries(actionColor)) {
    if (lower.includes(key)) return color;
  }
  return 'gray';
}

/** Render a details value in a human-friendly way */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(formatValue).join(', ');
  return JSON.stringify(value);
}

/** Convert snake_case / camelCase key to a readable label */
function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function ExpandableDetailsRow({ entry }: { entry: AuditEntry }) {
  const [opened, setOpened] = useState(false);
  const hasDetails = entry.details && Object.keys(entry.details).length > 0;

  return (
    <>
      <Table.Tr
        style={{ cursor: hasDetails ? 'pointer' : undefined }}
        onClick={() => hasDetails && setOpened((o) => !o)}
      >
        <Table.Td>
          <TimeAgo date={entry.timestamp} size="sm" />
        </Table.Td>
        <Table.Td>
          <Group gap={4}>
            <Text size="sm">{entry.actor}</Text>
            {entry.actor_type && (
              <Badge variant="dot" size="xs" color={entry.actor_type === 'system' ? 'gray' : entry.actor_type === 'agent' ? 'violet' : 'blue'}>
                {entry.actor_type}
              </Badge>
            )}
          </Group>
        </Table.Td>
        <Table.Td>
          <Badge variant="light" color={getActionColor(entry.action)}>{entry.action}</Badge>
        </Table.Td>
        <Table.Td>
          <Group gap={4}>
            <Badge variant="outline" size="sm" color="gray">{entry.resource_type}</Badge>
            <Text span size="xs" c="dimmed" truncate style={{ maxWidth: 120 }}>{entry.resource_id}</Text>
          </Group>
        </Table.Td>
        <Table.Td>
          {hasDetails ? (
            <ActionIcon variant="subtle" size="sm">
              {opened ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
            </ActionIcon>
          ) : (
            <Text size="xs" c="dimmed">—</Text>
          )}
        </Table.Td>
      </Table.Tr>
      {hasDetails && (
        <Table.Tr>
          <Table.Td colSpan={5} p={0} style={{ borderTop: 'none' }}>
            <Collapse in={opened}>
              <Paper p="sm" ml="md" mr="md" mb="xs" bg="var(--mantine-color-dark-7)" radius="sm">
                <Stack gap={4}>
                  {Object.entries(entry.details).map(([key, value]) => (
                    <Group key={key} gap="xs" wrap="nowrap" align="flex-start">
                      <Text size="xs" fw={500} c="dimmed" style={{ minWidth: 120, flexShrink: 0 }}>
                        {formatKey(key)}
                      </Text>
                      <Text size="xs" style={{ wordBreak: 'break-all' }}>
                        {formatValue(value)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>
            </Collapse>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

export function Component() {
  const { data: resp, isLoading } = useAuditListAuditEntries();
  const [filter, setFilter] = useState('');

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const entries = (resp?.data ?? []) as AuditEntry[];
  const filtered = entries.filter((e) =>
    e.actor?.toLowerCase().includes(filter.toLowerCase())
    || e.action?.toLowerCase().includes(filter.toLowerCase())
    || e.resource_type?.toLowerCase().includes(filter.toLowerCase()),
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
              <Table.Th w={40}>Details</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filtered.map((e) => (
              <ExpandableDetailsRow key={e.entry_id} entry={e} />
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
