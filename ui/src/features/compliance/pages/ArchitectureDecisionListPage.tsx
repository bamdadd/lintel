import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
  Box, Text, TypographyStylesProvider,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPencil } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@/features/chat/chat-markdown.css';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { architectureDecisionHooks, regulationHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface ADRItem {
  decision_id: string;
  project_id: string;
  title: string;
  status: string;
  context: string;
  decision: string;
  consequences: string;
  alternatives: string;
  superseded_by: string;
  regulation_ids: string[];
  tags: string[];
  date_proposed: string;
  date_decided: string;
  deciders: string[];
}
interface ProjectItem { project_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'proposed', label: 'Proposed' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'deprecated', label: 'Deprecated' },
  { value: 'superseded', label: 'Superseded' },
];

const statusColor: Record<string, string> = {
  proposed: 'yellow',
  accepted: 'green',
  deprecated: 'orange',
  superseded: 'gray',
};

function MarkdownField({
  label,
  value,
  onChange,
  editing,
  onToggle,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  editing: boolean;
  onToggle: () => void;
}) {
  return (
    <Box>
      <Group justify="space-between" mb={4}>
        <Text size="sm" fw={500}>{label}</Text>
        <ActionIcon variant="subtle" size="sm" onClick={onToggle} title={editing ? 'Preview' : 'Edit'}>
          <IconPencil size={14} />
        </ActionIcon>
      </Group>
      {editing ? (
        <Textarea
          value={value}
          onChange={(e) => onChange(e.currentTarget.value)}
          minRows={3}
          autosize
          placeholder="Markdown supported..."
        />
      ) : value ? (
        <Box
          p="sm"
          style={{
            border: '1px solid var(--mantine-color-dark-4)',
            borderRadius: 'var(--mantine-radius-sm)',
            cursor: 'pointer',
          }}
          onClick={onToggle}
        >
          <TypographyStylesProvider>
            <div className="chat-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
            </div>
          </TypographyStylesProvider>
        </Box>
      ) : (
        <Text
          size="sm"
          c="dimmed"
          p="sm"
          style={{
            border: '1px dashed var(--mantine-color-dark-4)',
            borderRadius: 'var(--mantine-radius-sm)',
            cursor: 'pointer',
          }}
          onClick={onToggle}
        >
          Click to add {label.toLowerCase()}...
        </Text>
      )}
    </Box>
  );
}

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = architectureDecisionHooks.useList(
    filterProject || undefined,
  );
  const { data: regResp } = regulationHooks.useList(filterProject || undefined);
  const createMut = architectureDecisionHooks.useCreate();
  const updateMut = architectureDecisionHooks.useUpdate();
  const removeMut = architectureDecisionHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<ADRItem | null>(null);
  const [editingContext, setEditingContext] = useState(false);
  const [editingDecision, setEditingDecision] = useState(false);
  const [editingConsequences, setEditingConsequences] = useState(false);
  const [editingAlternatives, setEditingAlternatives] = useState(false);

  const regulations = (regResp?.data ?? []) as unknown as {
    regulation_id: string;
    name: string;
  }[];
  const regOptions = regulations.map((r) => ({
    value: r.regulation_id,
    label: r.name,
  }));
  const projectOptions = [
    { value: '', label: 'All Projects' },
    ...projects.map((p) => ({ value: p.project_id, label: p.name })),
  ];

  const form = useForm({
    initialValues: {
      title: '',
      project_id: '',
      status: 'proposed',
      context: '',
      decision: '',
      consequences: '',
      alternatives: '',
      regulation_ids: [] as string[],
      tags: [] as string[],
      deciders: [] as string[],
    },
    validate: {
      title: (v) => (v.trim() ? null : 'Required'),
      project_id: (v) => (v ? null : 'Required'),
    },
  });

  const editForm = useForm({
    initialValues: {
      title: '',
      status: 'proposed',
      context: '',
      decision: '',
      consequences: '',
      alternatives: '',
      superseded_by: '',
      regulation_ids: [] as string[],
      tags: [] as string[],
      deciders: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as ADRItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => {
        notifications.show({
          title: 'Created',
          message: 'Architecture decision recorded',
          color: 'green',
        });
        form.reset();
        setCreating(false);
      },
    });
  });

  const openEdit = (item: ADRItem) => {
    setEditItem(item);
    setEditingContext(false);
    setEditingDecision(false);
    setEditingConsequences(false);
    setEditingAlternatives(false);
    editForm.setValues({
      title: item.title,
      status: item.status,
      context: item.context,
      decision: item.decision,
      consequences: item.consequences,
      alternatives: item.alternatives,
      superseded_by: item.superseded_by,
      regulation_ids: item.regulation_ids ?? [],
      tags: item.tags ?? [],
      deciders: item.deciders ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate(
      { id: editItem.decision_id, data: values as any },
      {
        onSuccess: () => {
          notifications.show({
            title: 'Updated',
            message: 'Decision updated',
            color: 'green',
          });
          setEditItem(null);
        },
      },
    );
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Architecture Decisions</Title>
        <Group>
          <Select
            placeholder="Filter by project"
            data={projectOptions}
            value={filterProject}
            onChange={(v) => setFilterProject(v ?? '')}
            searchable
            clearable
            w={220}
          />
          <Button onClick={() => setCreating(true)}>New ADR</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState
          title="No architecture decisions"
          description="Record important architectural decisions and their rationale"
          actionLabel="New ADR"
          onAction={() => setCreating(true)}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Title</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Deciders</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr
                key={item.decision_id}
                style={{ cursor: 'pointer' }}
                onClick={() => openEdit(item)}
              >
                <Table.Td fw={500}>{item.title}</Table.Td>
                <Table.Td>
                  <Badge
                    color={statusColor[item.status] ?? 'gray'}
                    variant="light"
                    size="sm"
                  >
                    {item.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {(item.deciders ?? []).join(', ') || '—'}
                </Table.Td>
                <Table.Td>
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeMut.mutate(item.decision_id);
                    }}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create modal */}
      <Modal
        opened={creating}
        onClose={() => setCreating(false)}
        title="New Architecture Decision"
        size="lg"
      >
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Title" {...form.getInputProps('title')} />
            <Select
              label="Project"
              data={projects.map((p) => ({
                value: p.project_id,
                label: p.name,
              }))}
              searchable
              {...form.getInputProps('project_id')}
            />
            <Select
              label="Status"
              data={STATUS_OPTIONS}
              {...form.getInputProps('status')}
            />
            <Textarea
              label="Context"
              placeholder="What is the issue motivating this decision?"
              autosize
              minRows={2}
              {...form.getInputProps('context')}
            />
            <Textarea
              label="Decision"
              placeholder="What is the change that we're proposing?"
              autosize
              minRows={2}
              {...form.getInputProps('decision')}
            />
            <Textarea
              label="Consequences"
              placeholder="What becomes easier or harder?"
              autosize
              minRows={2}
              {...form.getInputProps('consequences')}
            />
            <Textarea
              label="Alternatives Considered"
              placeholder="What other options were evaluated?"
              autosize
              minRows={2}
              {...form.getInputProps('alternatives')}
            />
            <MultiSelect
              label="Linked Regulations"
              data={regOptions}
              searchable
              {...form.getInputProps('regulation_ids')}
            />
            <Button type="submit" loading={createMut.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit modal */}
      <Modal
        opened={!!editItem}
        onClose={() => setEditItem(null)}
        title={`Edit: ${editItem?.title ?? ''}`}
        size="lg"
      >
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Title" {...editForm.getInputProps('title')} />
            <Select
              label="Status"
              data={STATUS_OPTIONS}
              {...editForm.getInputProps('status')}
            />
            <MarkdownField
              label="Context"
              value={editForm.values.context}
              onChange={(v) => editForm.setFieldValue('context', v)}
              editing={editingContext}
              onToggle={() => setEditingContext((v) => !v)}
            />
            <MarkdownField
              label="Decision"
              value={editForm.values.decision}
              onChange={(v) => editForm.setFieldValue('decision', v)}
              editing={editingDecision}
              onToggle={() => setEditingDecision((v) => !v)}
            />
            <MarkdownField
              label="Consequences"
              value={editForm.values.consequences}
              onChange={(v) => editForm.setFieldValue('consequences', v)}
              editing={editingConsequences}
              onToggle={() => setEditingConsequences((v) => !v)}
            />
            <MarkdownField
              label="Alternatives Considered"
              value={editForm.values.alternatives}
              onChange={(v) => editForm.setFieldValue('alternatives', v)}
              editing={editingAlternatives}
              onToggle={() => setEditingAlternatives((v) => !v)}
            />
            <TextInput
              label="Superseded By"
              placeholder="Decision ID that replaces this one"
              {...editForm.getInputProps('superseded_by')}
            />
            <MultiSelect
              label="Linked Regulations"
              data={regOptions}
              searchable
              {...editForm.getInputProps('regulation_ids')}
            />
            <Button type="submit" loading={updateMut.isPending}>
              Save
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
