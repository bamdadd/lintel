import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Badge,
  ActionIcon,
  Loader,
  Center,
  Select,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  useProjectsListProjects,
  useProjectsCreateProject,
  useProjectsRemoveProject,
} from '@/generated/api/projects/projects';
import { useRepositoriesListRepositories } from '@/generated/api/repositories/repositories';
import { EmptyState } from '@/shared/components/EmptyState';

interface Project {
  project_id: string;
  name: string;
  repo_id: string;
  status: string;
  default_branch: string;
}

export function Component() {
  const { data: resp, isLoading } = useProjectsListProjects();
  const { data: reposResp } = useRepositoriesListRepositories();
  const createMutation = useProjectsCreateProject();
  const deleteMutation = useProjectsRemoveProject();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      project_id: '',
      name: '',
      repo_id: '',
      default_branch: 'main',
    },
    validate: {
      project_id: (v) => (v.trim() ? null : 'Required'),
      name: (v) => (v.trim() ? null : 'Required'),
      repo_id: (v) => (v.trim() ? null : 'Required'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const projects = (resp?.data ?? []) as Project[];
  const repos = (reposResp?.data ?? []) as Array<{ repo_id: string; name?: string; url?: string }>;
  const repoOptions = repos.map((r) => ({ value: r.repo_id, label: r.name ?? r.url ?? r.repo_id }));

  const handleSubmit = form.onSubmit((values) => {
    createMutation.mutate(
      { data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: `Project "${values.name}" created`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/projects'] });
          form.reset();
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create project', color: 'red' });
        },
      },
    );
  });

  const handleDelete = (projectId: string) => {
    deleteMutation.mutate(
      { projectId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Project removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/projects'] });
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Projects</Title>
        <Button onClick={open}>Create Project</Button>
      </Group>

      {projects.length === 0 ? (
        <EmptyState
          title="No projects"
          description="Create a project to link a repository to a workflow"
          actionLabel="Create Project"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Repo</Table.Th>
              <Table.Th>Branch</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {projects.map((p) => (
              <Table.Tr key={p.project_id} style={{ cursor: 'pointer' }} onClick={() => void navigate(`/projects/${p.project_id}`)}>
                <Table.Td>{p.name}</Table.Td>
                <Table.Td>{p.repo_id}</Table.Td>
                <Table.Td>{p.default_branch}</Table.Td>
                <Table.Td><Badge>{p.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    onClick={(e) => { e.stopPropagation(); handleDelete(p.project_id); }}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Project">
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <TextInput label="Project ID" placeholder="my-project" {...form.getInputProps('project_id')} />
            <TextInput label="Name" placeholder="My Project" {...form.getInputProps('name')} />
            <Select
              label="Repository"
              placeholder="Select a repository"
              data={repoOptions}
              searchable
              {...form.getInputProps('repo_id')}
            />
            <TextInput label="Default Branch" {...form.getInputProps('default_branch')} />
            <Button type="submit" loading={createMutation.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
