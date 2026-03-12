import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, TagsInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { strategyHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface StrategyItem {
  strategy_id: string; project_id: string; name: string; description: string;
  objectives: string[]; owner: string; status: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' }, { value: 'active', label: 'Active' },
  { value: 'under_review', label: 'Under Review' }, { value: 'deprecated', label: 'Deprecated' },
];
const statusColor: Record<string, string> = { draft: 'gray', active: 'green', under_review: 'yellow', deprecated: 'orange' };

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = strategyHooks.useList(filterProject || undefined);
  const createMut = strategyHooks.useCreate();
  const updateMut = strategyHooks.useUpdate();
  const removeMut = strategyHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<StrategyItem | null>(null);

  const projectOptions = [{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];

  const form = useForm({
    initialValues: { name: '', project_id: '', description: '', objectives: [] as string[], owner: '', status: 'active', tags: [] as string[] },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: { name: '', description: '', objectives: [] as string[], owner: '', status: 'active', tags: [] as string[] },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as StrategyItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Strategy added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const openEdit = (item: StrategyItem) => {
    setEditItem(item);
    editForm.setValues({ name: item.name, description: item.description, objectives: item.objectives ?? [], owner: item.owner, status: item.status, tags: item.tags ?? [] });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.strategy_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'Strategy updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Strategies</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Strategy</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No strategies" description="Define testing, security, or development strategies" actionLabel="Add Strategy" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Objectives</Table.Th><Table.Th>Owner</Table.Th><Table.Th>Status</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.strategy_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td>{(item.objectives ?? []).length}</Table.Td>
                <Table.Td>{item.owner || '—'}</Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.strategy_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Strategy" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="e.g. Testing Strategy" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <TagsInput label="Objectives" placeholder="Add objective" {...form.getInputProps('objectives')} />
            <TextInput label="Owner" {...form.getInputProps('owner')} />
            <Select label="Status" data={STATUS_OPTIONS} {...form.getInputProps('status')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <TagsInput label="Objectives" {...editForm.getInputProps('objectives')} />
            <TextInput label="Owner" {...editForm.getInputProps('owner')} />
            <Select label="Status" data={STATUS_OPTIONS} {...editForm.getInputProps('status')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
