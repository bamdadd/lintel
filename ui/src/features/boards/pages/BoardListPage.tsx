import { Title, Stack, Loader, Center, Table, Text, Badge, Group, Button } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useBoardsListBoards } from '../api';
import type { Board } from '../api';
import { CreateBoardModal } from '../components/CreateBoardModal';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';

interface ProjectItem {
  project_id: string;
  name: string;
}

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const firstProjectId = projects[0]?.project_id;

  const { data: resp, isLoading } = useBoardsListBoards(firstProjectId);
  const navigate = useNavigate();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  const boards = (resp?.data ?? []) as Board[];

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Boards</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          New Board
        </Button>
      </Group>
      <CreateBoardModal opened={createOpened} onClose={closeCreate} />

      {boards.length === 0 ? (
        <EmptyState
          title="No boards"
          description="Create boards via the API to organise work items in a kanban view."
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Columns</Table.Th>
              <Table.Th>Project</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {boards.map((b) => (
              <Table.Tr
                key={b.board_id}
                style={{ cursor: 'pointer' }}
                onClick={() => void navigate(`/boards/${b.board_id}`)}
              >
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {b.name}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {b.columns.map((c) => (
                      <Badge key={c.column_id} size="xs" variant="light">
                        {c.name}
                      </Badge>
                    ))}
                    {b.columns.length === 0 && (
                      <Text size="xs" c="dimmed">
                        No columns
                      </Text>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {projects.find((p) => p.project_id === b.project_id)?.name ??
                      b.project_id}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
