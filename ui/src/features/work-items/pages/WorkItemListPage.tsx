import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select, Textarea,
  Loader, Center, ActionIcon, Badge, Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconExternalLink } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useWorkItemsListWorkItems,
  useWorkItemsCreateWorkItem,
  useWorkItemsUpdateWorkItem,
  useWorkItemsRemoveWorkItem,
} from '@/generated/api/work-items/work-items';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import type { WorkItemType } from '@/generated/models/workItemType';
import type { WorkItemStatus } from '@/generated/models/workItemStatus';
import { EmptyState } from '@/shared/components/EmptyState';

interface WorkItem {
  work_item_id: string;
  project_id: string;
  title: string;
  description: string;
  work_type: string;
  status: string;
  assignee_agent_role: string;
  branch_name: string;
  pr_url: string;
}

interface ProjectItem { project_id: string; name: string; }

const WORK_TYPES = [
  { value: 'feature', label: 'Feature' },
  { value: 'bug', label: 'Bug' },
  { value: 'refactor', label: 'Refactor' },
  { value: 'task', label: 'Task' },
];

const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'merged', label: 'Merged' },
  { value: 'closed', label: 'Closed' },
];

const statusColor: Record<string, string> = {
  open: 'blue', in_progress: 'yellow', in_review: 'orange', approved: 'green', merged: 'teal', closed: 'gray',
};

const typeColor: Record<string, string> = { feature: 'violet', bug: 'red', refactor: 'cyan', task: 'gray' };

export function Component() {
  const { data: resp, isLoading } = useWorkItemsListWorkItems();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = useWorkItemsCreateWorkItem();
  const updateMut = useWorkItemsUpdateWorkItem();
  const deleteMut = useWorkItemsRemoveWorkItem();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<WorkItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: { project_id: '', title: '', description: '', work_type: 'task', assignee_agent_role: '' },
    validate: { title: (v) => (v.trim() ? null : 'Required') },
  });

  const editFormState = useForm({
    initialValues: { title: '', description: '', work_type: 'task', status: 'open', assignee_agent_role: '', branch_name: '', pr_url: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const items = (resp?.data ?? []) as WorkItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      { data: { ...values, work_type: values.work_type as WorkItemType } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Work item created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
      },
    );
  });

  const openEdit = (w: WorkItem) => {
    setEditItem(w);
    editFormState.setValues({
      title: w.title, description: w.description, work_type: w.work_type,
      status: w.status, assignee_agent_role: w.assignee_agent_role ?? '',
      branch_name: w.branch_name ?? '', pr_url: w.pr_url ?? '',
    });
  };

  const handleEdit = editFormState.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate(
      { workItemId: editItem.work_item_id, data: { ...values, work_type: values.work_type as WorkItemType, status: values.status as WorkItemStatus } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Work item updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
          setEditItem(null);
        },
      },
    );
  });

  const handleDelete = (id: string) => {
    deleteMut.mutate({ workItemId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Work item removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
        if (editItem?.work_item_id === id) setEditItem(null);
      },
    });
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? id;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Work Items</Title>
        <Button onClick={open}>Create Work Item</Button>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No work items" description="Create work items to track features and bugs" actionLabel="Create Work Item" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Title</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Project</Table.Th>
              <Table.Th>Links</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((w) => (
              <Table.Tr key={w.work_item_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(w)}>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Badge color={typeColor[w.work_type] ?? 'gray'} variant="light" size="sm">{w.work_type}</Badge>
                    <Text size="sm" fw={500} truncate>{w.title}</Text>
                  </Group>
                </Table.Td>
                <Table.Td><Badge color={statusColor[w.status] ?? 'gray'}>{w.status?.replace('_', ' ')}</Badge></Table.Td>
                <Table.Td><Text size="sm">{projectName(w.project_id)}</Text></Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    {w.branch_name && (
                      <Badge variant="outline" size="sm" color="gray" radius="sm">{w.branch_name}</Badge>
                    )}
                    {w.pr_url && (
                      <ActionIcon
                        variant="subtle"
                        size="sm"
                        component="a"
                        href={w.pr_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                      >
                        <IconExternalLink size={14} />
                      </ActionIcon>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(w.work_item_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Work Item">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Title" placeholder="Implement feature X" {...form.getInputProps('title')} />
            <Textarea label="Description" minRows={3} {...form.getInputProps('description')} />
            <Select label="Type" data={WORK_TYPES} {...form.getInputProps('work_type')} />
            <Select label="Project" placeholder="Select project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <TextInput label="Assign to Agent Role" placeholder="coder" {...form.getInputProps('assignee_agent_role')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.title ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Title" {...editFormState.getInputProps('title')} />
            <Textarea label="Description" minRows={3} {...editFormState.getInputProps('description')} />
            <Group grow>
              <Select label="Type" data={WORK_TYPES} {...editFormState.getInputProps('work_type')} />
              <Select label="Status" data={STATUSES} {...editFormState.getInputProps('status')} />
            </Group>
            <TextInput label="Agent Role" {...editFormState.getInputProps('assignee_agent_role')} />
            <TextInput label="Branch" {...editFormState.getInputProps('branch_name')} />
            <TextInput label="PR URL" {...editFormState.getInputProps('pr_url')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
