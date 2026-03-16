import { Table, Badge, Text, Code } from '@mantine/core';
import type { FlowEntry } from '../types';
import { FLOW_TYPE_LABELS, FLOW_TYPE_COLORS } from '../types';

interface FlowTableProps {
  flows: FlowEntry[];
}

export function FlowTable({ flows }: FlowTableProps) {
  return (
    <Table striped highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Name</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Source</Table.Th>
          <Table.Th>Sink</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>Steps</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {flows.map((flow) => (
          <Table.Tr key={flow.flow_id}>
            <Table.Td>
              <Text size="sm" fw={500}>
                {flow.name}
              </Text>
            </Table.Td>
            <Table.Td>
              <Badge
                color={FLOW_TYPE_COLORS[flow.flow_type] ?? 'gray'}
                variant="light"
                size="sm"
              >
                {FLOW_TYPE_LABELS[flow.flow_type] ?? flow.flow_type}
              </Badge>
            </Table.Td>
            <Table.Td>
              <Code>
                {flow.source.function_name}
              </Code>
              <Text size="xs" c="dimmed">
                {flow.source.file_path}:{flow.source.line_number}
              </Text>
            </Table.Td>
            <Table.Td>
              {flow.sink ? (
                <>
                  <Badge size="xs" variant="outline">
                    {flow.sink.step_type}
                  </Badge>
                  <Text size="xs" c="dimmed">
                    {flow.sink.description?.slice(0, 60)}
                  </Text>
                </>
              ) : (
                <Text size="xs" c="dimmed">—</Text>
              )}
            </Table.Td>
            <Table.Td style={{ textAlign: 'right' }}>
              {flow.steps.length}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
