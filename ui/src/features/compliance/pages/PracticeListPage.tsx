import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { practiceHooks, procedureHooks, strategyHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface PracticeItem {
  practice_id: string; project_id: string; name: string; description: string;
  procedure_ids: string[]; strategy_ids: string[]; evidence_type: string;
  automation_status: string; status: string; risk_level: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' }, { value: 'active', label: 'Active' },
  { value: 'under_review', label: 'Under Review' }, { value: 'deprecated', label: 'Deprecated' },
];
const RISK_OPTIONS = [
  { value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' }, { value: 'critical', label: 'Critical' },
];
const AUTOMATION_OPTIONS = [
  { value: 'manual', label: 'Manual' }, { value: 'semi_automated', label: 'Semi-Automated' },
  { value: 'fully_automated', label: 'Fully Automated' },
];
const riskColor: Record<string, string> = { low: 'green', medium: 'yellow', high: 'orange', critical: 'red' };
const statusColor: Record<string, string> = { draft: 'gray', active: 'green', under_review: 'yellow', deprecated: 'orange' };
const autoColor: Record<string, string> = { manual: 'orange', semi_automated: 'yellow', fully_automated: 'green' };

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = practiceHooks.useList(filterProject || undefined);
  const { data: procResp } = procedureHooks.useList(filterProject || undefined);
  const { data: stratResp } = strategyHooks.useList(filterProject || undefined);
  const createMut = practiceHooks.useCreate();
  const updateMut = practiceHooks.useUpdate();
  const removeMut = practiceHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<PracticeItem | null>(null);

  const procedures = (procResp?.data ?? []) as unknown as { procedure_id: string; name: string }[];
  const strategies = (stratResp?.data ?? []) as unknown as { strategy_id: string; name: string }[];
  const procOptions = procedures.map((p) => ({ value: p.procedure_id, label: p.name }));
  const stratOptions = strategies.map((s) => ({ value: s.strategy_id, label: s.name }));
  const projectOptions = [{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', procedure_ids: [] as string[],
      strategy_ids: [] as string[], evidence_type: '', automation_status: 'manual',
      status: 'active', risk_level: 'low', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', procedure_ids: [] as string[], strategy_ids: [] as string[],
      evidence_type: '', automation_status: 'manual', status: 'active', risk_level: 'low', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as PracticeItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Practice added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const openEdit = (item: PracticeItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, description: item.description,
      procedure_ids: item.procedure_ids ?? [], strategy_ids: item.strategy_ids ?? [],
      evidence_type: item.evidence_type, automation_status: item.automation_status,
      status: item.status, risk_level: item.risk_level, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.practice_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'Practice updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Practices</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Practice</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No practices" description="Practices are concrete implementations of procedures, driven by strategy" actionLabel="Add Practice" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Automation</Table.Th>
            <Table.Th>Risk</Table.Th><Table.Th>Status</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.practice_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td><Badge color={autoColor[item.automation_status] ?? 'gray'} variant="light" size="sm">{item.automation_status || '—'}</Badge></Table.Td>
                <Table.Td><Badge color={riskColor[item.risk_level]} variant="dot" size="sm">{item.risk_level}</Badge></Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.practice_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Practice" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <MultiSelect label="Linked Procedures" data={procOptions} searchable {...form.getInputProps('procedure_ids')} />
            <MultiSelect label="Linked Strategies" data={stratOptions} searchable {...form.getInputProps('strategy_ids')} />
            <TextInput label="Evidence Type" placeholder="test_results, code_review, audit_log" {...form.getInputProps('evidence_type')} />
            <Select label="Automation Status" data={AUTOMATION_OPTIONS} {...form.getInputProps('automation_status')} />
            <Group grow>
              <Select label="Risk Level" data={RISK_OPTIONS} {...form.getInputProps('risk_level')} />
              <Select label="Status" data={STATUS_OPTIONS} {...form.getInputProps('status')} />
            </Group>
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <MultiSelect label="Linked Procedures" data={procOptions} searchable {...editForm.getInputProps('procedure_ids')} />
            <MultiSelect label="Linked Strategies" data={stratOptions} searchable {...editForm.getInputProps('strategy_ids')} />
            <Select label="Automation Status" data={AUTOMATION_OPTIONS} {...editForm.getInputProps('automation_status')} />
            <Group grow>
              <Select label="Risk Level" data={RISK_OPTIONS} {...editForm.getInputProps('risk_level')} />
              <Select label="Status" data={STATUS_OPTIONS} {...editForm.getInputProps('status')} />
            </Group>
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
