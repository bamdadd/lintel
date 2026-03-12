import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect, TagsInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { procedureHooks, compliancePolicyHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface ProcedureItem {
  procedure_id: string; project_id: string; name: string; description: string;
  policy_ids: string[]; workflow_definition_id: string; steps: string[];
  owner: string; status: string; risk_level: string; tags: string[];
}
interface ProjectItem { project_id: string; name: string; }
interface PolicyItem { policy_id: string; name: string; }

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

  const { data: resp, isLoading } = procedureHooks.useList(filterProject || undefined);
  const { data: polResp } = compliancePolicyHooks.useList(filterProject || undefined);
  const createMut = procedureHooks.useCreate();
  const updateMut = procedureHooks.useUpdate();
  const removeMut = procedureHooks.useRemove();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<ProcedureItem | null>(null);

  const policies = (polResp?.data ?? []) as unknown as PolicyItem[];
  const policyOptions = policies.map((p) => ({ value: p.policy_id, label: p.name }));
  const projectOptions = [{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', policy_ids: [] as string[],
      workflow_definition_id: '', steps: [] as string[], owner: '',
      status: 'draft', risk_level: 'medium', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', policy_ids: [] as string[],
      workflow_definition_id: '', steps: [] as string[], owner: '',
      status: 'draft', risk_level: 'medium', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const items = (resp?.data ?? []) as unknown as ProcedureItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Procedure added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const openEdit = (item: ProcedureItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, description: item.description, policy_ids: item.policy_ids ?? [],
      workflow_definition_id: item.workflow_definition_id, steps: item.steps ?? [],
      owner: item.owner, status: item.status, risk_level: item.risk_level, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.procedure_id, data: values as any }, {
      onSuccess: () => { notifications.show({ title: 'Updated', message: 'Procedure updated', color: 'green' }); setEditItem(null); },
    });
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Procedures</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button onClick={() => setCreating(true)}>Add Procedure</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No procedures" description="Procedures implement compliance policies step by step" actionLabel="Add Procedure" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Name</Table.Th><Table.Th>Policies</Table.Th><Table.Th>Steps</Table.Th>
            <Table.Th>Risk</Table.Th><Table.Th>Status</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.procedure_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td>{(item.policy_ids ?? []).length} linked</Table.Td>
                <Table.Td>{(item.steps ?? []).length} steps</Table.Td>
                <Table.Td><Badge color={riskColor[item.risk_level]} variant="dot" size="sm">{item.risk_level}</Badge></Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.procedure_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Procedure" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <MultiSelect label="Linked Policies" data={policyOptions} searchable {...form.getInputProps('policy_ids')} />
            <TextInput label="Workflow Definition ID" placeholder="Link to a workflow (optional)" {...form.getInputProps('workflow_definition_id')} />
            <TagsInput label="Steps" placeholder="Add a step and press Enter" {...form.getInputProps('steps')} />
            <TextInput label="Owner" {...form.getInputProps('owner')} />
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
            <MultiSelect label="Linked Policies" data={policyOptions} searchable {...editForm.getInputProps('policy_ids')} />
            <TextInput label="Workflow Definition ID" {...editForm.getInputProps('workflow_definition_id')} />
            <TagsInput label="Steps" placeholder="Add a step" {...editForm.getInputProps('steps')} />
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
