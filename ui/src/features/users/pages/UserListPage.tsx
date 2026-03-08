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
  useUsersListUsers,
  useUsersCreateUser,
  useUsersUpdateUser,
  useUsersDeleteUser,
} from '@/generated/api/users/users';
import { useTeamsListTeams } from '@/generated/api/teams/teams';
import type { UserRole } from '@/generated/models/userRole';
import { EmptyState } from '@/shared/components/EmptyState';

interface UserItem {
  user_id: string;
  name: string;
  email: string;
  role: string;
  slack_user_id: string;
  team_ids: string[];
}

interface TeamItem { team_id: string; name: string; }

export function Component() {
  const { data: resp, isLoading } = useUsersListUsers();
  const { data: teamsResp } = useTeamsListTeams();
  const createMutation = useUsersCreateUser();
  const updateMutation = useUsersUpdateUser();
  const deleteMutation = useUsersDeleteUser();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editUser, setEditUser] = useState<UserItem | null>(null);

  const teams = (teamsResp?.data ?? []) as unknown as TeamItem[];
  const teamOptions = teams.map((t) => ({ value: t.team_id, label: t.name }));

  const form = useForm({
    initialValues: { name: '', email: '', role: 'member', slack_user_id: '', team_ids: [] as string[] },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: { name: '', email: '', role: 'member', slack_user_id: '', team_ids: [] as string[] },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const users = (resp?.data ?? []) as unknown as UserItem[];

  const handleSubmit = form.onSubmit((values) => {
    createMutation.mutate(
      { data: { ...values, role: values.role as UserRole } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: `User "${values.name}" added`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/users'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create user', color: 'red' }),
      },
    );
  });

  const openEdit = (u: UserItem) => {
    setEditUser(u);
    editForm.setValues({
      name: u.name, email: u.email ?? '', role: u.role ?? 'member',
      slack_user_id: u.slack_user_id ?? '', team_ids: u.team_ids ?? [],
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editUser) return;
    updateMutation.mutate(
      { userId: editUser.user_id, data: { ...values, role: values.role as UserRole } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: `User "${values.name}" updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/users'] });
          setEditUser(null);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to update user', color: 'red' }),
      },
    );
  });

  const handleDelete = (userId: string) => {
    deleteMutation.mutate(
      { userId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'User removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/users'] });
          if (editUser?.user_id === userId) setEditUser(null);
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Users</Title>
        <Button onClick={open}>Add User</Button>
      </Group>

      {users.length === 0 ? (
        <EmptyState title="No users" description="Add users to assign them to teams and projects" actionLabel="Add User" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Email</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Teams</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users.map((u) => (
              <Table.Tr key={u.user_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(u)}>
                <Table.Td>{u.name}</Table.Td>
                <Table.Td>{u.email || '—'}</Table.Td>
                <Table.Td><Badge>{u.role}</Badge></Table.Td>
                <Table.Td>{u.team_ids?.length ?? 0}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(u.user_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Add User">
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="Jane Doe" {...form.getInputProps('name')} />
            <TextInput label="Email" placeholder="jane@example.com" {...form.getInputProps('email')} />
            <Select label="Role" data={[{ value: 'admin', label: 'Admin' }, { value: 'member', label: 'Member' }, { value: 'viewer', label: 'Viewer' }]} {...form.getInputProps('role')} />
            <TextInput label="Slack User ID" placeholder="U01234ABC" {...form.getInputProps('slack_user_id')} />
            <MultiSelect label="Teams" placeholder="Assign to teams" data={teamOptions} searchable {...form.getInputProps('team_ids')} />
            <Button type="submit" loading={createMutation.isPending}>Add User</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editUser} onClose={() => setEditUser(null)} title={`Edit: ${editUser?.name ?? ''}`}>
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <TextInput label="Email" {...editForm.getInputProps('email')} />
            <Select label="Role" data={[{ value: 'admin', label: 'Admin' }, { value: 'member', label: 'Member' }, { value: 'viewer', label: 'Viewer' }]} {...editForm.getInputProps('role')} />
            <TextInput label="Slack User ID" {...editForm.getInputProps('slack_user_id')} />
            <MultiSelect label="Teams" data={teamOptions} searchable {...editForm.getInputProps('team_ids')} />
            <Button type="submit" loading={updateMutation.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
