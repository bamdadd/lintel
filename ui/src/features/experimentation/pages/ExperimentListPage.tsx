import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { experimentHooks, strategyHooks, kpiHooks } from '@/features/compliance/api';
import { EmptyState } from '@/shared/components/EmptyState';

interface ExperimentItem {
  experiment_id: string; project_id: string; name: string; hypothesis: string;
  description: string; strategy_ids: string[]; kpi_ids: string[];
  status: string; start_date: string; end_date: string; outcome: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'planned', label: 'Planned' }, { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' }, { value: 'cancelled', label: 'Cancelled' },
];
const statusColor: Record<string, string> = { planned: 'gray', running: 'blue', completed: 'green', cancelled: 'red' };

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = experimentHooks.useList(filterProject || undefined);
  const { data: stratResp } = strategyHooks.useList(filterProject || undefined);
  const { data: kpiResp } = kpiHooks.useList(filterProject || undefined);
  const createMut = experimentHooks.useCreate();
  const updateMut = experimentHooks.useUpdate();
  const removeMut = experimentHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<ExperimentItem | null>(null);

  const strategies = (stratResp?.data ?? []) as unknown as { strategy_id: string; name: string }[];
  const kpis = (kpiResp?.data ?? []) as unknown as { kpi_id: string; name: string }[];
  const stratOptions = strategies.map((s) => ({ value: s.strategy_id, label: s.name }));
  const kpiOptions = kpis.map((k) => ({ value: k.kpi_id, label: k.name }));

  const form = useForm({
    initialValues: {
      name: '', project_id: '', hypothesis: '', description: '',
      strategy_ids: [] as string[], kpi_ids: [] as string[], status: 'planned',
      start_date: '', end_date: '', outcome: '', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', hypothesis: '', description: '', strategy_ids: [] as string[],
      kpi_ids: [] as string[], status: 'planned', start_date: '', end_date: '', outcome: '', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as ExperimentItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Experiment added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const openEdit = (item: ExperimentItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, hypothesis: item.hypothesis, description: item.description,
      strategy_ids: item.strategy_ids ?? [], kpi_ids: item.kpi_ids ?? [],
      status: item.status, start_date: item.start_date, end_date: item.end_date,
      outcome: item.outcome, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.experiment_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'Experiment updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Experiments</Title>
        <Group>
          <Select placeholder="Filter by project" data={[{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))]} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Experiment</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No experiments" description="Track experiments with hypotheses, KPIs, and outcomes" actionLabel="Add Experiment" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Hypothesis</Table.Th><Table.Th>Status</Table.Th><Table.Th>Dates</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.experiment_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td maw={300} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.hypothesis || '—'}</Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>{item.start_date || '—'} {item.end_date ? `to ${item.end_date}` : ''}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.experiment_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Experiment" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Hypothesis" autosize minRows={2} {...form.getInputProps('hypothesis')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <MultiSelect label="Linked Strategies" data={stratOptions} searchable {...form.getInputProps('strategy_ids')} />
            <MultiSelect label="KPIs to Measure" data={kpiOptions} searchable {...form.getInputProps('kpi_ids')} />
            <Select label="Status" data={STATUS_OPTIONS} {...form.getInputProps('status')} />
            <Group grow>
              <TextInput label="Start Date" placeholder="YYYY-MM-DD" {...form.getInputProps('start_date')} />
              <TextInput label="End Date" placeholder="YYYY-MM-DD" {...form.getInputProps('end_date')} />
            </Group>
            <Textarea label="Outcome" autosize minRows={2} {...form.getInputProps('outcome')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Hypothesis" autosize minRows={2} {...editForm.getInputProps('hypothesis')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <Select label="Status" data={STATUS_OPTIONS} {...editForm.getInputProps('status')} />
            <Textarea label="Outcome" autosize minRows={2} {...editForm.getInputProps('outcome')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
