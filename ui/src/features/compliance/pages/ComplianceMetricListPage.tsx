import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { complianceMetricHooks, kpiHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface MetricItem {
  metric_id: string; project_id: string; name: string; description: string;
  value: string; unit: string; source: string; kpi_ids: string[];
  collected_at: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }

const SOURCE_OPTIONS = [
  { value: 'automated', label: 'Automated' }, { value: 'manual', label: 'Manual' },
  { value: 'agent', label: 'Agent-Collected' },
];

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = complianceMetricHooks.useList(filterProject || undefined);
  const { data: kpiResp } = kpiHooks.useList(filterProject || undefined);
  const createMut = complianceMetricHooks.useCreate();
  const removeMut = complianceMetricHooks.useRemove();
  const [creating, setCreating] = useState(false);

  const kpis = (kpiResp?.data ?? []) as unknown as { kpi_id: string; name: string }[];
  const kpiOptions = kpis.map((k) => ({ value: k.kpi_id, label: k.name }));

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', value: '', unit: '',
      source: 'automated', kpi_ids: [] as string[], collected_at: '', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as MetricItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Metric added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const sourceColor: Record<string, string> = { automated: 'green', manual: 'yellow', agent: 'blue' };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Compliance Metrics</Title>
        <Group>
          <Select placeholder="Filter by project" data={[{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))]} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Metric</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No metrics" description="Collect compliance metrics manually or via agents" actionLabel="Add Metric" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Value</Table.Th><Table.Th>Source</Table.Th><Table.Th>Collected</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.metric_id}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td>{item.value} {item.unit}</Table.Td>
                <Table.Td><Badge color={sourceColor[item.source] ?? 'gray'} variant="light" size="sm">{item.source || '—'}</Badge></Table.Td>
                <Table.Td>{item.collected_at || '—'}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={() => removeMut.mutate(item.metric_id)}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Metric" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <Group grow>
              <TextInput label="Value" {...form.getInputProps('value')} />
              <TextInput label="Unit" {...form.getInputProps('unit')} />
            </Group>
            <Select label="Source" data={SOURCE_OPTIONS} {...form.getInputProps('source')} />
            <MultiSelect label="Linked KPIs" data={kpiOptions} searchable {...form.getInputProps('kpi_ids')} />
            <TextInput label="Collected At" placeholder="YYYY-MM-DD" {...form.getInputProps('collected_at')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
