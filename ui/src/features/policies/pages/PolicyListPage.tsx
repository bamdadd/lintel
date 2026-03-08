import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  usePoliciesListPolicies,
  usePoliciesCreatePolicy,
  usePoliciesUpdatePolicy,
  usePoliciesDeletePolicy,
} from '@/generated/api/policies/policies';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useUsersListUsers } from '@/generated/api/users/users';
import { EmptyState } from '@/shared/components/EmptyState';
import type { PolicyAction } from '@/generated/models/policyAction';

interface PolicyItem {
  policy_id: string;
  name: string;
  event_type: string;
  condition: string;
  action: string;
  approvers: string[];
  project_id: string;
}

interface ProjectItem { project_id: string; name: string; }
interface UserItem { user_id: string; name: string; }

const POLICY_ACTIONS = [
  { value: 'require_approval', label: 'Require Approval' },
  { value: 'auto_approve', label: 'Auto Approve' },
  { value: 'block', label: 'Block' },
  { value: 'notify', label: 'Notify' },
];

const actionColor: Record<string, string> = { require_approval: 'yellow', auto_approve: 'green', block: 'red', notify: 'blue' };

export function Component() {
  const { data: resp, isLoading } = usePoliciesListPolicies();
  const { data: projectsResp } = useProjectsListProjects();
  const { data: usersResp } = useUsersListUsers();
  const createMut = usePoliciesCreatePolicy();
  const updateMut = usePoliciesUpdatePolicy();
  const deleteMut = usePoliciesDeletePolicy();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<PolicyItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const users = (usersResp?.data ?? []) as unknown as UserItem[];
  const projectOptions = [{ value: '', label: '— Global —' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];
  const userOptions = users.map((u) => ({ value: u.user_id, label: u.name }));

  const form = useForm({
    initialValues: { name: '', event_type: '', condition: '', action: 'require_approval', approvers: [] as string[], project_id: '' },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editFormState = useForm({
    initialValues: { name: '', event_type: '', condition: '', action: 'require_approval', approvers: [] as string[], project_id: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const policies = (resp?.data ?? []) as PolicyItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      { data: { ...values, action: values.action as PolicyAction } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Policy created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/policies'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
      },
    );
  });

  const openEdit = (p: PolicyItem) => {
    setEditItem(p);
    editFormState.setValues({ name: p.name, event_type: p.event_type, condition: p.condition, action: p.action, approvers: p.approvers ?? [], project_id: p.project_id });
  };

  const handleEdit = editFormState.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate(
      { policyId: editItem.policy_id, data: { ...values, action: values.action as PolicyAction } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Policy updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/policies'] });
          setEditItem(null);
        },
      },
    );
  });

  const handleDelete = (id: string) => {
    deleteMut.mutate({ policyId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Policy removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/policies'] });
        if (editItem?.policy_id === id) setEditItem(null);
      },
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Policies</Title>
        <Button onClick={open}>Create Policy</Button>
      </Group>

      {policies.length === 0 ? (
        <EmptyState title="No policies" description="Create policies to control workflow approvals" actionLabel="Create Policy" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Event</Table.Th>
              <Table.Th>Action</Table.Th>
              <Table.Th>Approvers</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {policies.map((p) => (
              <Table.Tr key={p.policy_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(p)}>
                <Table.Td>{p.name}</Table.Td>
                <Table.Td><Badge variant="light">{p.event_type || '—'}</Badge></Table.Td>
                <Table.Td><Badge color={actionColor[p.action] ?? 'gray'}>{p.action}</Badge></Table.Td>
                <Table.Td>{p.approvers?.length ?? 0}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(p.policy_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Policy" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="Code review required" {...form.getInputProps('name')} />
            <TextInput label="Event Type" placeholder="code.pushed" {...form.getInputProps('event_type')} />
            <TextInput label="Condition" placeholder="branch == 'main'" {...form.getInputProps('condition')} />
            <Select label="Action" data={POLICY_ACTIONS} {...form.getInputProps('action')} />
            <MultiSelect label="Approvers" placeholder="Select approvers" data={userOptions} searchable {...form.getInputProps('approvers')} />
            <Select label="Project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editFormState.getInputProps('name')} />
            <TextInput label="Event Type" {...editFormState.getInputProps('event_type')} />
            <TextInput label="Condition" {...editFormState.getInputProps('condition')} />
            <Select label="Action" data={POLICY_ACTIONS} {...editFormState.getInputProps('action')} />
            <MultiSelect label="Approvers" data={userOptions} searchable {...editFormState.getInputProps('approvers')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
