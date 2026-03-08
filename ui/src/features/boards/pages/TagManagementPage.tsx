import { useState } from 'react';
import {
  Title,
  Stack,
  Loader,
  Center,
  Table,
  Text,
  Group,
  Button,
  ActionIcon,
  Modal,
  TextInput,
  ColorInput,
  Select,
  ColorSwatch,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconPlus, IconPencil, IconTrash, IconCheck, IconX } from '@tabler/icons-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';

interface Tag {
  tag_id: string;
  project_id: string;
  name: string;
  color: string;
}

interface ListResponse<T> {
  data: T[];
  status: number;
  headers: Headers;
}

interface SingleResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

interface ProjectItem {
  project_id: string;
  name: string;
}

function useTagsList(projectId?: string) {
  return useQuery({
    queryKey: ['/api/v1/tags', projectId],
    queryFn: () =>
      customInstance<ListResponse<Tag>>(
        projectId ? `/api/v1/projects/${projectId}/tags` : '/api/v1/tags',
      ),
    enabled: !!projectId,
  });
}

function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { project_id: string; name: string; color: string }) =>
      customInstance<SingleResponse<Tag>>('/api/v1/tags', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/tags'] }),
  });
}

function useUpdateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tagId, data }: { tagId: string; data: { name?: string; color?: string } }) =>
      customInstance<SingleResponse<Tag>>(`/api/v1/tags/${tagId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/tags'] }),
  });
}

function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) =>
      customInstance<undefined>(`/api/v1/tags/${tagId}`, { method: 'DELETE' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/tags'] }),
  });
}

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const projectId = selectedProjectId ?? projects[0]?.project_id;

  const { data: resp, isLoading } = useTagsList(projectId);
  const tags = (resp?.data ?? []) as Tag[];

  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState('#228be6');

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');

  const createTag = useCreateTag();
  const updateTag = useUpdateTag();
  const deleteTag = useDeleteTag();

  const handleCreate = () => {
    if (!projectId || !newName.trim()) return;
    createTag.mutate(
      { project_id: projectId, name: newName.trim(), color: newColor },
      {
        onSuccess: () => {
          setNewName('');
          setNewColor('#228be6');
          closeCreate();
        },
      },
    );
  };

  const handleSaveEdit = (tagId: string) => {
    updateTag.mutate(
      { tagId, data: { name: editName.trim(), color: editColor } },
      { onSuccess: () => setEditingId(null) },
    );
  };

  const startEdit = (tag: Tag) => {
    setEditingId(tag.tag_id);
    setEditName(tag.name);
    setEditColor(tag.color);
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Tags</Title>
        <Group>
          <Select
            placeholder="Filter by project"
            data={projects.map((p) => ({ value: p.project_id, label: p.name }))}
            value={projectId ?? null}
            onChange={setSelectedProjectId}
            clearable={false}
            w={200}
          />
          <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
            New Tag
          </Button>
        </Group>
      </Group>

      {isLoading ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : tags.length === 0 ? (
        <EmptyState title="No tags" description="Create tags to categorise work items." />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Color</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th w={100}>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {tags.map((tag) => (
              <Table.Tr key={tag.tag_id}>
                <Table.Td w={80}>
                  {editingId === tag.tag_id ? (
                    <ColorInput size="xs" value={editColor} onChange={setEditColor} w={120} />
                  ) : (
                    <ColorSwatch color={tag.color} size={20} />
                  )}
                </Table.Td>
                <Table.Td>
                  {editingId === tag.tag_id ? (
                    <TextInput size="xs" value={editName} onChange={(e) => setEditName(e.currentTarget.value)} w={200} />
                  ) : (
                    <Text size="sm">{tag.name}</Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {editingId === tag.tag_id ? (
                    <Group gap={4}>
                      <ActionIcon
                        color="green"
                        variant="subtle"
                        onClick={() => handleSaveEdit(tag.tag_id)}
                        loading={updateTag.isPending}
                      >
                        <IconCheck size={16} />
                      </ActionIcon>
                      <ActionIcon color="gray" variant="subtle" onClick={() => setEditingId(null)}>
                        <IconX size={16} />
                      </ActionIcon>
                    </Group>
                  ) : (
                    <Group gap={4}>
                      <ActionIcon variant="subtle" onClick={() => startEdit(tag)}>
                        <IconPencil size={16} />
                      </ActionIcon>
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => deleteTag.mutate(tag.tag_id)}
                        loading={deleteTag.isPending}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpened} onClose={closeCreate} title="Create Tag">
        <Stack gap="sm">
          <TextInput
            label="Name"
            placeholder="Tag name"
            value={newName}
            onChange={(e) => setNewName(e.currentTarget.value)}
            required
          />
          <ColorInput label="Color" value={newColor} onChange={setNewColor} />
          <Button onClick={handleCreate} loading={createTag.isPending} disabled={!newName.trim()}>
            Create
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
