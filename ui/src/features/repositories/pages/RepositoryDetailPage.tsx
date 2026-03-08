import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import {
  Title, Stack, Paper, Text, Group, Button, Loader, Center,
  TextInput, Select, Modal,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useRepositoriesGetRepository,
  useRepositoriesUpdateRepository,
  useRepositoriesRemoveRepository,
} from '@/generated/api/repositories/repositories';
import { StatusBadge } from '@/shared/components/StatusBadge';
import type { RepoStatus } from '@/generated/models/repoStatus';

interface RepoData {
  repo_id: string;
  name: string;
  url: string;
  default_branch: string;
  owner: string;
  provider: string;
  status: string;
}

export function Component() {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);

  const { data: resp, isLoading } = useRepositoriesGetRepository(repoId ?? '', {
    query: { enabled: !!repoId },
  });
  const updateMut = useRepositoriesUpdateRepository();
  const deleteMut = useRepositoriesRemoveRepository();

  const form = useForm({
    initialValues: { name: '', default_branch: '', owner: '', status: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const repo = resp?.data as RepoData | undefined;
  if (!repo) return <Text>Repository not found</Text>;

  const startEdit = () => {
    form.setValues({
      name: repo.name ?? '',
      default_branch: repo.default_branch ?? 'main',
      owner: repo.owner ?? '',
      status: repo.status ?? 'active',
    });
    setEditing(true);
  };

  const handleSave = form.onSubmit((values) => {
    updateMut.mutate(
      { repoId: repo.repo_id, data: { ...values, status: values.status as RepoStatus } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Repository updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/repositories'] });
          setEditing(false);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' }),
      },
    );
  });

  const handleDelete = () => {
    deleteMut.mutate(
      { repoId: repo.repo_id },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Repository removed', color: 'orange' });
          void navigate('/repositories');
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/repositories')}>&larr; Back</Button>
        <Title order={2}>{repo.name}</Title>
        <StatusBadge status={repo.status ?? 'active'} />
      </Group>

      <Paper withBorder p="lg" radius="md">
        <Stack gap="xs">
          <Text><strong>URL:</strong> {repo.url}</Text>
          <Text><strong>Default Branch:</strong> {repo.default_branch}</Text>
          <Text><strong>Owner:</strong> {repo.owner || '—'}</Text>
          <Text><strong>Provider:</strong> {repo.provider || 'github'}</Text>
        </Stack>
      </Paper>

      <Group>
        <Button onClick={startEdit}>Edit</Button>
        <Button color="red" variant="light" onClick={handleDelete} loading={deleteMut.isPending}>Delete</Button>
      </Group>

      <Modal opened={editing} onClose={() => setEditing(false)} title="Edit Repository">
        <form onSubmit={handleSave}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <TextInput label="Default Branch" {...form.getInputProps('default_branch')} />
            <TextInput label="Owner" {...form.getInputProps('owner')} />
            <Select label="Status" data={[
              { value: 'active', label: 'Active' },
              { value: 'archived', label: 'Archived' },
              { value: 'error', label: 'Error' },
            ]} {...form.getInputProps('status')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
