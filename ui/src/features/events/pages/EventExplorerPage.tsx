import {
  Title,
  Stack,
  Table,
  Loader,
  Center,
  Select,
  Group,
  Code,
} from '@mantine/core';
import { useState } from 'react';
import { useEventsListEvents, useEventsListEventTypes } from '@/generated/api/events/events';
import { EmptyState } from '@/shared/components/EmptyState';

export function Component() {
  const { data: eventsResp, isLoading: eventsLoading } = useEventsListEvents();
  const { data: typesResp } = useEventsListEventTypes();
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const events = eventsResp?.data;
  const eventTypes = typesResp?.data ?? [];

  if (eventsLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Event Explorer</Title>
        <Select
          placeholder="Filter by type"
          clearable
          data={eventTypes.map((t: string) => t)}
          w={250}
        />
      </Group>

      {!events || events.length === 0 ? (
        <EmptyState
          title="No events yet"
          description="Events will appear as workflows process messages."
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>#</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Details</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {events.map((event, i) => (
              <Table.Tr
                key={i}
                onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                style={{ cursor: 'pointer' }}
              >
                <Table.Td>{i + 1}</Table.Td>
                <Table.Td>{String(event.event_type ?? 'unknown')}</Table.Td>
                <Table.Td>
                  {expandedRow === i ? (
                    <Code block>{JSON.stringify(event, null, 2)}</Code>
                  ) : (
                    String(event.task_name ?? JSON.stringify(event).slice(0, 80))
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
