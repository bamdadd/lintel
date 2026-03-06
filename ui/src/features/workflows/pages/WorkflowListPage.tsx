import { Title, Stack, Table, Loader, Center, Button, Group } from '@mantine/core';
import { useNavigate } from 'react-router';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';
import { EmptyState } from '@/shared/components/EmptyState';

export function Component() {
  const { data: resp, isLoading } = useWorkflowDefinitionsListWorkflowDefinitions();
  const navigate = useNavigate();
  const definitions = resp?.data;

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Workflows</Title>
        <Button onClick={() => void navigate('/workflows/editor')}>
          New Workflow
        </Button>
      </Group>

      {!definitions || definitions.length === 0 ? (
        <EmptyState
          title="No workflow definitions"
          description="Create your first workflow definition."
          actionLabel="Create Workflow"
          onAction={() => void navigate('/workflows/editor')}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Template</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {definitions.map((d, i) => (
              <Table.Tr
                key={i}
                style={{ cursor: 'pointer' }}
                onClick={() => void navigate(`/workflows/editor/${String(d.definition_id ?? '')}`)}
              >
                <Table.Td>{String(d.definition_id ?? '')}</Table.Td>
                <Table.Td>{String(d.name ?? '')}</Table.Td>
                <Table.Td>{String(d.description ?? '')}</Table.Td>
                <Table.Td>{d.is_template ? 'Yes' : 'No'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
