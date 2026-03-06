import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Loader,
  Center,
  ActionIcon,
  Badge,
  MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useTeamsListTeams,
  useTeamsCreateTeam,
  useTeamsUpdateTeam,
  useTeamsDeleteTeam,
} from '@/generated/api/teams/teams';
import { useUsersListUsers } from '@/generated/api/users/users';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';

interface TeamItem {
  team_id: string;
  name: string;
  member_ids: string[];
  project_ids: string[];
}

interface UserItem {
  user_id: string;
  name: string;
}

interface ProjectItem {
  project_id: string;
  name: string;
}

export function Component() {
  const { data: resp, isLoading } = useTeamsListTeams();
  const { data: usersResp } = useUsersListUsers();
  const { data: projectsResp } = useProjectsListProjects();
  const createMutation = useTeamsCreateTeam();
  const updateMutation = useTeamsUpdateTeam();
  const deleteMutation = useTeamsDeleteTeam();
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [editTeam, setEditTeam] = useState<TeamItem | null>(null);

  const users = (usersResp?.data ?? []) as UserItem[];
  const projects = (projectsResp?.data ?? []) as ProjectItem[];
  const userOptions = users.map((u) => ({ value: u.user_id, label: u.name }));
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const createForm = useForm({
    initialValues: { name: '' },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '',
      member_ids: [] as string[],
      project_ids: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const teams = (resp?.data ?? []) as TeamItem[];

  const handleCreate = createForm.onSubmit((values) => {
    createMutation.mutate(
      { data: { name: values.name } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: `Team "${values.name}" created`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/teams'] });
          createForm.reset();
          closeCreate();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create team', color: 'red' });
        },
      },
    );
  });

  const openEdit = (team: TeamItem) => {
    setEditTeam(team);
    editForm.setValues({
      name: team.name,
      member_ids: team.member_ids ?? [],
      project_ids: team.project_ids ?? [],
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editTeam) return;
    updateMutation.mutate(
      { teamId: editTeam.team_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: `Team "${values.name}" updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/teams'] });
          setEditTeam(null);
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update team', color: 'red' });
        },
      },
    );
  });

  const handleDelete = (teamId: string) => {
    deleteMutation.mutate(
      { teamId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Team removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/teams'] });
          if (editTeam?.team_id === teamId) setEditTeam(null);
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Teams</Title>
        <Button onClick={openCreate}>Create Team</Button>
      </Group>

      {teams.length === 0 ? (
        <EmptyState
          title="No teams"
          description="Create teams to organize users and projects"
          actionLabel="Create Team"
          onAction={openCreate}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Members</Table.Th>
              <Table.Th>Projects</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {teams.map((t) => (
              <Table.Tr key={t.team_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(t)}>
                <Table.Td>{t.name}</Table.Td>
                <Table.Td><Badge variant="light">{t.member_ids?.length ?? 0} members</Badge></Table.Td>
                <Table.Td><Badge variant="light">{t.project_ids?.length ?? 0} projects</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(t.team_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create — just name */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Team">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="Engineering" {...createForm.getInputProps('name')} />
            <Button type="submit" loading={createMutation.isPending}>Create Team</Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit — manage members and projects */}
      <Modal opened={!!editTeam} onClose={() => setEditTeam(null)} title={`Manage: ${editTeam?.name ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <MultiSelect
              label="Members"
              placeholder="Add users to this team"
              data={userOptions}
              searchable
              {...editForm.getInputProps('member_ids')}
            />
            <MultiSelect
              label="Projects"
              placeholder="Assign projects to this team"
              data={projectOptions}
              searchable
              {...editForm.getInputProps('project_ids')}
            />
            <Button type="submit" loading={updateMutation.isPending}>Save Changes</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
