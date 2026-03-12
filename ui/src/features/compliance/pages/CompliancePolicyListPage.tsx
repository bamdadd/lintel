import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { compliancePolicyHooks, regulationHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface PolicyItem {
  policy_id: string; project_id: string; name: string; description: string;
  regulation_ids: string[]; owner: string; status: string; risk_level: string;
  review_date: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }
interface RegItem { regulation_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' }, { value: 'active', label: 'Active' },
  { value: 'under_review', label: 'Under Review' }, { value: 'deprecated', label: 'Deprecated' },
];
const RISK_OPTIONS = [
  { value: 'low', label: 'Low' }, { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' }, { value: 'critical', label: 'Critical' },
];
const riskColor: Record<string, string> = { low: 'green', medium: 'yellow', high: 'orange', critical: 'red' };
const statusColor: Record<string, string> = { draft: 'gray', active: 'green', under_review: 'yellow', deprecated: 'orange' };

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = compliancePolicyHooks.useList(filterProject || undefined);
  const { data: regsResp } = regulationHooks.useList(filterProject || undefined);
  const createMut = compliancePolicyHooks.useCreate();
  const updateMut = compliancePolicyHooks.useUpdate();
  const removeMut = compliancePolicyHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<PolicyItem | null>(null);

  const regs = (regsResp?.data ?? []) as unknown as RegItem[];
  const regOptions = regs.map((r) => ({ value: r.regulation_id, label: r.name }));
  const projectOptions = [{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];
  const projectRequired = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', regulation_ids: [] as string[],
      owner: '', status: 'draft', risk_level: 'medium', review_date: '', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', regulation_ids: [] as string[], owner: '',
      status: 'draft', risk_level: 'medium', review_date: '', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const items = (resp?.data ?? []) as unknown as PolicyItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Policy added', color: 'green' }); form.reset(); setCreating(false); },
      onError: () => notifications.show({ title: 'Error', message: 'Failed', color: 'red' }),
    });
  });

  const openEdit = (item: PolicyItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, description: item.description, regulation_ids: item.regulation_ids ?? [],
      owner: item.owner, status: item.status, risk_level: item.risk_level,
      review_date: item.review_date, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.policy_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'Policy updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Compliance Policies</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Policy</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No compliance policies" description="Define policies that interpret your regulations" actionLabel="Add Policy" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Regulations</Table.Th><Table.Th>Owner</Table.Th>
            <Table.Th>Risk</Table.Th><Table.Th>Status</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.policy_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td>{(item.regulation_ids ?? []).length} linked</Table.Td>
                <Table.Td>{item.owner || '—'}</Table.Td>
                <Table.Td><Badge color={riskColor[item.risk_level]} variant="dot" size="sm">{item.risk_level}</Badge></Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.policy_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Compliance Policy" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="e.g. Secure Coding Policy" {...form.getInputProps('name')} />
            <Select label="Project" data={projectRequired} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <MultiSelect label="Linked Regulations" data={regOptions} searchable {...form.getInputProps('regulation_ids')} />
            <TextInput label="Owner" {...form.getInputProps('owner')} />
            <Group grow>
              <Select label="Risk Level" data={RISK_OPTIONS} {...form.getInputProps('risk_level')} />
              <Select label="Status" data={STATUS_OPTIONS} {...form.getInputProps('status')} />
            </Group>
            <TextInput label="Review Date" placeholder="YYYY-MM-DD" {...form.getInputProps('review_date')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <MultiSelect label="Linked Regulations" data={regOptions} searchable {...editForm.getInputProps('regulation_ids')} />
            <TextInput label="Owner" {...editForm.getInputProps('owner')} />
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
