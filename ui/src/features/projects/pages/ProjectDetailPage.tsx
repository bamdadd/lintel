import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import {
  Title, Stack, Paper, Text, Group, Button, Badge, Loader, Center,
  TextInput, MultiSelect, Select, Modal,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useProjectsGetProject,
  useProjectsUpdateProject,
  useProjectsRemoveProject,
} from '@/generated/api/projects/projects';
import { useRepositoriesListRepositories } from '@/generated/api/repositories/repositories';
import { useAiProvidersListAiProviders } from '@/generated/api/ai-providers/ai-providers';

interface ProjectData {
  project_id: string;
  name: string;
  repo_ids: string[];
  channel_id: string;
  workspace_id: string;
  workflow_definition_id: string;
  default_branch: string;
  ai_provider_id: string;
  status: string;
}

interface RepoItem { repo_id: string; name: string; }
interface ProviderItem { provider_id: string; name: string; }

export function Component() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);

  const { data: resp, isLoading } = useProjectsGetProject(projectId ?? '', {
    query: { enabled: !!projectId },
  });
  const { data: reposResp } = useRepositoriesListRepositories();
  const { data: providersResp } = useAiProvidersListAiProviders();
  const updateMut = useProjectsUpdateProject();
  const deleteMut = useProjectsRemoveProject();

  const repos = (reposResp?.data ?? []) as RepoItem[];
  const providers = (providersResp?.data ?? []) as ProviderItem[];
  const repoOptions = repos.map((r) => ({ value: r.repo_id, label: r.name }));
  const providerOptions = [{ value: '', label: '— None —' }, ...providers.map((p) => ({ value: p.provider_id, label: p.name }))];

  const form = useForm({
    initialValues: { name: '', repo_ids: [] as string[], default_branch: '', channel_id: '', workspace_id: '', ai_provider_id: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const project = resp?.data as ProjectData | undefined;
  if (!project) return <Text>Project not found</Text>;

  const repoNames = (project.repo_ids ?? []).map(
    (id) => repos.find((r) => r.repo_id === id)?.name ?? id,
  );
  const providerName = providers.find((p) => p.provider_id === project.ai_provider_id)?.name ?? project.ai_provider_id;

  const startEdit = () => {
    form.setValues({
      name: project.name,
      repo_ids: project.repo_ids ?? [],
      default_branch: project.default_branch ?? 'main',
      channel_id: project.channel_id ?? '',
      workspace_id: project.workspace_id ?? '',
      ai_provider_id: project.ai_provider_id ?? '',
    });
    setEditing(true);
  };

  const handleSave = form.onSubmit((values) => {
    updateMut.mutate(
      { projectId: project.project_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Project updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/projects'] });
          setEditing(false);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' }),
      },
    );
  });

  const handleDelete = () => {
    deleteMut.mutate(
      { projectId: project.project_id },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Project removed', color: 'orange' });
          void navigate('/projects');
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/projects')}>&larr; Back</Button>
        <Title order={2}>{project.name}</Title>
        <Badge>{project.status}</Badge>
      </Group>

      <Paper withBorder p="lg" radius="md">
        <Stack gap="xs">
          <Group gap="xs">
            <Text><strong>Repositories:</strong></Text>
            {repoNames.length > 0
              ? repoNames.map((name) => (
                  <Badge key={name} size="sm" variant="light">{name}</Badge>
                ))
              : <Text c="dimmed">—</Text>}
          </Group>
          <Text><strong>Default Branch:</strong> {project.default_branch}</Text>
          <Text><strong>Workflow:</strong> {project.workflow_definition_id || '—'}</Text>
          <Text><strong>AI Provider:</strong> {providerName || '—'}</Text>
          <Text><strong>Channel:</strong> {project.channel_id || '—'}</Text>
          <Text><strong>Workspace:</strong> {project.workspace_id || '—'}</Text>
        </Stack>
      </Paper>

      <Group>
        <Button onClick={startEdit}>Edit</Button>
        <Button color="red" variant="light" onClick={handleDelete} loading={deleteMut.isPending}>Delete</Button>
      </Group>

      <Modal opened={editing} onClose={() => setEditing(false)} title="Edit Project" size="lg">
        <form onSubmit={handleSave}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <MultiSelect label="Repositories" data={repoOptions} searchable {...form.getInputProps('repo_ids')} />
            <TextInput label="Default Branch" {...form.getInputProps('default_branch')} />
            <Select label="AI Provider" data={providerOptions} searchable {...form.getInputProps('ai_provider_id')} />
            <TextInput label="Channel ID" {...form.getInputProps('channel_id')} />
            <TextInput label="Workspace ID" {...form.getInputProps('workspace_id')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
