import { useState, useMemo } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select, Textarea,
  Loader, Center, ActionIcon, Badge, Text, TypographyStylesProvider, Box,
  Paper, SegmentedControl, Tooltip, SimpleGrid, ThemeIcon, Drawer, Divider,
  ScrollArea, Tabs,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure, useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconExternalLink, IconPencil, IconPlus, IconSearch,
  IconGitBranch, IconListCheck,
} from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@/features/chat/chat-markdown.css';
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
import { StatusBadge } from '@/shared/components/StatusBadge';

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
  const [editingDescription, setEditingDescription] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const isMobile = useMediaQuery('(max-width: 768px)');

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: { project_id: '', title: '', description: '', work_type: 'task', assignee_agent_role: '' },
    validate: { title: (v) => (v.trim() ? null : 'Required') },
  });

  const editFormState = useForm({
    initialValues: { title: '', description: '', work_type: 'task', status: 'open', assignee_agent_role: '', branch_name: '', pr_url: '' },
  });

  const allItems = (resp?.data ?? []) as WorkItem[];

  // Status counts for filter badges
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const w of allItems) {
      counts[w.status] = (counts[w.status] ?? 0) + 1;
    }
    return counts;
  }, [allItems]);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const items = allItems.filter((w) => {
    if (typeFilter !== 'all' && w.work_type !== typeFilter) return false;
    if (statusFilter !== 'all' && w.status !== statusFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return w.title.toLowerCase().includes(s) || w.description?.toLowerCase().includes(s);
    }
    return true;
  });

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
    setEditingDescription(false);
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
    <Stack gap="lg">
      <Group justify="space-between">
        <Group gap="xs">
          <Title order={2}>Work Items</Title>
          <Badge variant="light" size="lg">{allItems.length}</Badge>
        </Group>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>
          Create Work Item
        </Button>
      </Group>

      {allItems.length === 0 ? (
        <EmptyState title="No work items" description="Create work items to track features and bugs" actionLabel="Create Work Item" onAction={open} />
      ) : (
        <>
          {/* Filters row */}
          <Group gap="sm" wrap="wrap">
            <TextInput
              placeholder="Search work items..."
              leftSection={<IconSearch size={16} />}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
              style={{ flex: 1, minWidth: 200 }}
            />
            <SegmentedControl
              size="xs"
              value={typeFilter}
              onChange={setTypeFilter}
              data={[
                { value: 'all', label: 'All Types' },
                ...WORK_TYPES.map((t) => ({ value: t.value, label: t.label })),
              ]}
            />
          </Group>

          {/* Status filter chips */}
          <Group gap={6}>
            <Badge
              variant={statusFilter === 'all' ? 'filled' : 'outline'}
              color="gray"
              style={{ cursor: 'pointer' }}
              onClick={() => setStatusFilter('all')}
            >
              All ({allItems.length})
            </Badge>
            {STATUSES.map((s) => (
              <Badge
                key={s.value}
                variant={statusFilter === s.value ? 'filled' : 'outline'}
                color={statusFilter === s.value ? 'indigo' : 'gray'}
                style={{ cursor: 'pointer' }}
                onClick={() => setStatusFilter(statusFilter === s.value ? 'all' : s.value)}
              >
                {s.label} ({statusCounts[s.value] ?? 0})
              </Badge>
            ))}
          </Group>

          <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Title</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Project</Table.Th>
                  <Table.Th>Links</Table.Th>
                  <Table.Th w={60} />
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
                    <Table.Td><StatusBadge status={w.status} /></Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{projectName(w.project_id)}</Text></Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        {w.branch_name && (
                          <Tooltip label={w.branch_name}>
                            <Badge variant="outline" size="sm" color="gray" radius="sm" leftSection={<IconGitBranch size={10} />}>
                              {w.branch_name.length > 20 ? `${w.branch_name.slice(0, 20)}...` : w.branch_name}
                            </Badge>
                          </Tooltip>
                        )}
                        {w.pr_url && (
                          <Tooltip label="Open PR">
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
                          </Tooltip>
                        )}
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label="Delete">
                        <ActionIcon color="red" variant="subtle" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(w.work_item_id); }}>
                          <IconTrash size={14} />
                        </ActionIcon>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                ))}
                {items.length === 0 && (
                  <Table.Tr>
                    <Table.Td colSpan={5}>
                      <Text c="dimmed" ta="center" py="md">No work items match your filters</Text>
                    </Table.Td>
                  </Table.Tr>
                )}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}

      {/* Create Modal */}
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

      {/* Edit Drawer — full-height side panel instead of modal */}
      <Drawer
        opened={!!editItem}
        onClose={() => setEditItem(null)}
        title={
          <Group gap="xs">
            <Badge color={typeColor[editItem?.work_type ?? ''] ?? 'gray'} variant="light" size="sm">
              {editItem?.work_type}
            </Badge>
            <Text fw={600} truncate>{editItem?.title}</Text>
          </Group>
        }
        position="right"
        size={isMobile ? '100%' : 520}
        padding="lg"
      >
        {editItem && (
          <form onSubmit={handleEdit}>
            <Stack gap="md">
              <TextInput label="Title" {...editFormState.getInputProps('title')} />

              <Box>
                <Group justify="space-between" mb={4}>
                  <Text size="sm" fw={500}>Description</Text>
                  <ActionIcon
                    variant="subtle"
                    size="sm"
                    onClick={() => setEditingDescription((v) => !v)}
                    title={editingDescription ? 'Preview' : 'Edit'}
                  >
                    <IconPencil size={14} />
                  </ActionIcon>
                </Group>
                {editingDescription ? (
                  <Textarea minRows={6} autosize placeholder="Markdown supported..." {...editFormState.getInputProps('description')} />
                ) : editFormState.values.description ? (
                  <Paper
                    withBorder
                    p="sm"
                    radius="sm"
                    style={{ cursor: 'pointer' }}
                    onClick={() => setEditingDescription(true)}
                  >
                    <TypographyStylesProvider>
                      <div className="chat-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {editFormState.values.description}
                        </ReactMarkdown>
                      </div>
                    </TypographyStylesProvider>
                  </Paper>
                ) : (
                  <Text
                    size="sm"
                    c="dimmed"
                    p="sm"
                    style={{
                      border: '1px dashed var(--mantine-color-default-border)',
                      borderRadius: 'var(--mantine-radius-sm)',
                      cursor: 'pointer',
                    }}
                    onClick={() => setEditingDescription(true)}
                  >
                    Click to add a description...
                  </Text>
                )}
              </Box>

              <Divider />

              <SimpleGrid cols={2}>
                <Select label="Type" data={WORK_TYPES} {...editFormState.getInputProps('work_type')} />
                <Select label="Status" data={STATUSES} {...editFormState.getInputProps('status')} />
              </SimpleGrid>
              <TextInput label="Agent Role" placeholder="coder" {...editFormState.getInputProps('assignee_agent_role')} />
              <TextInput
                label="Branch"
                leftSection={<IconGitBranch size={14} />}
                {...editFormState.getInputProps('branch_name')}
              />
              <TextInput
                label="PR URL"
                leftSection={<IconExternalLink size={14} />}
                {...editFormState.getInputProps('pr_url')}
              />

              <Group>
                <Button type="submit" loading={updateMut.isPending} style={{ flex: 1 }}>
                  Save Changes
                </Button>
                <Tooltip label="Delete work item">
                  <ActionIcon
                    color="red"
                    variant="light"
                    size="lg"
                    onClick={() => handleDelete(editItem.work_item_id)}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Stack>
          </form>
        )}
      </Drawer>
    </Stack>
  );
}
