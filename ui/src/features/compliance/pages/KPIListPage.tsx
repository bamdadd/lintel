import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect, Progress, Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { kpiHooks, strategyHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface KPIItem {
  kpi_id: string; project_id: string; name: string; description: string;
  target_value: string; current_value: string; unit: string; direction: string;
  strategy_ids: string[]; threshold_warning: string; threshold_critical: string;
  status: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }

const DIRECTION_OPTIONS = [
  { value: 'increase', label: 'Increase' }, { value: 'decrease', label: 'Decrease' },
  { value: 'maintain', label: 'Maintain' },
];

function kpiProgress(kpi: KPIItem): { value: number; color: string } {
  const current = parseFloat(kpi.current_value) || 0;
  const target = parseFloat(kpi.target_value) || 100;
  if (target === 0) return { value: 0, color: 'gray' };
  const pct = Math.min((current / target) * 100, 100);
  const warn = parseFloat(kpi.threshold_warning) || target * 0.7;
  const crit = parseFloat(kpi.threshold_critical) || target * 0.4;
  let color = 'green';
  if (kpi.direction === 'decrease') {
    color = current <= target ? 'green' : current <= warn ? 'yellow' : 'red';
  } else {
    color = current >= target ? 'green' : current >= warn ? 'yellow' : 'red';
  }
  return { value: pct, color };
}

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = kpiHooks.useList(filterProject || undefined);
  const { data: stratResp } = strategyHooks.useList(filterProject || undefined);
  const createMut = kpiHooks.useCreate();
  const updateMut = kpiHooks.useUpdate();
  const removeMut = kpiHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<KPIItem | null>(null);

  const strategies = (stratResp?.data ?? []) as unknown as { strategy_id: string; name: string }[];
  const stratOptions = strategies.map((s) => ({ value: s.strategy_id, label: s.name }));

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', target_value: '', current_value: '',
      unit: '', direction: 'increase', strategy_ids: [] as string[],
      threshold_warning: '', threshold_critical: '', status: 'active', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', target_value: '', current_value: '', unit: '',
      direction: 'increase', strategy_ids: [] as string[],
      threshold_warning: '', threshold_critical: '', status: 'active', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as KPIItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'KPI added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const openEdit = (item: KPIItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, description: item.description, target_value: item.target_value,
      current_value: item.current_value, unit: item.unit, direction: item.direction,
      strategy_ids: item.strategy_ids ?? [], threshold_warning: item.threshold_warning,
      threshold_critical: item.threshold_critical, status: item.status, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.kpi_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'KPI updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>KPIs</Title>
        <Group>
          <Select placeholder="Filter by project" data={[{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))]} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add KPI</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No KPIs" description="Track key performance indicators for your project" actionLabel="Add KPI" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Current / Target</Table.Th><Table.Th>Progress</Table.Th><Table.Th>Direction</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => {
              const prog = kpiProgress(item);
              return (
                <Table.Tr key={item.kpi_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                  <Table.Td fw={500}>{item.name}</Table.Td>
                  <Table.Td>{item.current_value || '—'} / {item.target_value || '—'} {item.unit}</Table.Td>
                  <Table.Td w={150}><Progress value={prog.value} color={prog.color} size="lg" radius="xl" /></Table.Td>
                  <Table.Td><Badge variant="light" size="sm">{item.direction}</Badge></Table.Td>
                  <Table.Td>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.kpi_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add KPI" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <Group grow>
              <TextInput label="Target Value" {...form.getInputProps('target_value')} />
              <TextInput label="Current Value" {...form.getInputProps('current_value')} />
              <TextInput label="Unit" placeholder="%, ms, count" {...form.getInputProps('unit')} />
            </Group>
            <Select label="Direction" data={DIRECTION_OPTIONS} {...form.getInputProps('direction')} />
            <MultiSelect label="Linked Strategies" data={stratOptions} searchable {...form.getInputProps('strategy_ids')} />
            <Group grow>
              <TextInput label="Warning Threshold" {...form.getInputProps('threshold_warning')} />
              <TextInput label="Critical Threshold" {...form.getInputProps('threshold_critical')} />
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
            <Group grow>
              <TextInput label="Target Value" {...editForm.getInputProps('target_value')} />
              <TextInput label="Current Value" {...editForm.getInputProps('current_value')} />
              <TextInput label="Unit" {...editForm.getInputProps('unit')} />
            </Group>
            <Select label="Direction" data={DIRECTION_OPTIONS} {...editForm.getInputProps('direction')} />
            <MultiSelect label="Linked Strategies" data={stratOptions} searchable {...editForm.getInputProps('strategy_ids')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
