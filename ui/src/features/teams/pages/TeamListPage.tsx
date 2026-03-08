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
  Checkbox,
  Text,
  ScrollArea,
  Paper,
  Tabs,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconUsers, IconBriefcase } from '@tabler/icons-react';
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
  email?: string;
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
  const [memberFilter, setMemberFilter] = useState('');
  const [projectFilter, setProjectFilter] = useState('');

  const users = (usersResp?.data ?? []) as unknown as UserItem[];
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];

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

  const teams = (resp?.data ?? []) as unknown as TeamItem[];

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
    setMemberFilter('');
    setProjectFilter('');
    editForm.setValues({
      name: team.name,
      member_ids: team.member_ids ?? [],
      project_ids: team.project_ids ?? [],
    });
  };

  const toggleMember = (userId: string) => {
    const current = editForm.values.member_ids;
    if (current.includes(userId)) {
      editForm.setFieldValue('member_ids', current.filter((id) => id !== userId));
    } else {
      editForm.setFieldValue('member_ids', [...current, userId]);
    }
  };

  const toggleProject = (projectId: string) => {
    const current = editForm.values.project_ids;
    if (current.includes(projectId)) {
      editForm.setFieldValue('project_ids', current.filter((id) => id !== projectId));
    } else {
      editForm.setFieldValue('project_ids', [...current, projectId]);
    }
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

  const filteredUsers = users.filter((u) =>
    u.name.toLowerCase().includes(memberFilter.toLowerCase())
    || (u.email ?? '').toLowerCase().includes(memberFilter.toLowerCase())
  );

  const filteredProjects = projects.filter((p) =>
    p.name.toLowerCase().includes(projectFilter.toLowerCase())
  );

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

      {/* Edit — manage members and projects with checkbox lists */}
      <Modal opened={!!editTeam} onClose={() => setEditTeam(null)} title={`Manage: ${editTeam?.name ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="md">
            <TextInput label="Name" {...editForm.getInputProps('name')} />

            <Tabs defaultValue="members">
              <Tabs.List>
                <Tabs.Tab value="members" leftSection={<IconUsers size={16} />}>
                  Members ({editForm.values.member_ids.length})
                </Tabs.Tab>
                <Tabs.Tab value="projects" leftSection={<IconBriefcase size={16} />}>
                  Projects ({editForm.values.project_ids.length})
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="members" pt="sm">
                <Stack gap="xs">
                  <TextInput
                    placeholder="Search users..."
                    size="sm"
                    value={memberFilter}
                    onChange={(e) => setMemberFilter(e.currentTarget.value)}
                  />
                  <ScrollArea h={250}>
                    <Stack gap={4}>
                      {filteredUsers.length === 0 ? (
                        <Text size="sm" c="dimmed" ta="center" py="md">
                          {users.length === 0 ? 'No users created yet' : 'No matching users'}
                        </Text>
                      ) : (
                        filteredUsers.map((u) => (
                          <Paper key={u.user_id} p="xs" withBorder style={{ cursor: 'pointer' }}
                            onClick={() => toggleMember(u.user_id)}
                          >
                            <Group gap="sm">
                              <Checkbox
                                checked={editForm.values.member_ids.includes(u.user_id)}
                                onChange={() => toggleMember(u.user_id)}
                                onClick={(e) => e.stopPropagation()}
                              />
                              <div>
                                <Text size="sm" fw={500}>{u.name}</Text>
                                {u.email && <Text size="xs" c="dimmed">{u.email}</Text>}
                              </div>
                            </Group>
                          </Paper>
                        ))
                      )}
                    </Stack>
                  </ScrollArea>
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="projects" pt="sm">
                <Stack gap="xs">
                  <TextInput
                    placeholder="Search projects..."
                    size="sm"
                    value={projectFilter}
                    onChange={(e) => setProjectFilter(e.currentTarget.value)}
                  />
                  <ScrollArea h={250}>
                    <Stack gap={4}>
                      {filteredProjects.length === 0 ? (
                        <Text size="sm" c="dimmed" ta="center" py="md">
                          {projects.length === 0 ? 'No projects created yet' : 'No matching projects'}
                        </Text>
                      ) : (
                        filteredProjects.map((p) => (
                          <Paper key={p.project_id} p="xs" withBorder style={{ cursor: 'pointer' }}
                            onClick={() => toggleProject(p.project_id)}
                          >
                            <Group gap="sm">
                              <Checkbox
                                checked={editForm.values.project_ids.includes(p.project_id)}
                                onChange={() => toggleProject(p.project_id)}
                                onClick={(e) => e.stopPropagation()}
                              />
                              <Text size="sm" fw={500}>{p.name}</Text>
                            </Group>
                          </Paper>
                        ))
                      )}
                    </Stack>
                  </ScrollArea>
                </Stack>
              </Tabs.Panel>
            </Tabs>

            <Button type="submit" loading={updateMutation.isPending}>Save Changes</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
