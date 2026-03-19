import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import {
  Title, Stack, Paper, Text, Group, Button, Loader, Center,
  TextInput, Select, Modal, Tabs, Table, Badge, Anchor,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useRepositoriesGetRepository,
  useRepositoriesUpdateRepository,
  useRepositoriesRemoveRepository,
} from '@/generated/api/repositories/repositories';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { customInstance } from '@/shared/api/client';
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

interface Commit {
  sha: string;
  message: string;
  author: string;
  date: string;
}

interface PullRequest {
  number: number;
  title: string;
  state: string;
  author: string;
  created_at: string;
  updated_at: string;
  html_url: string;
  head_branch: string;
  base_branch: string;
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

  const { data: commitsResp, isLoading: commitsLoading } = useQuery({
    queryKey: ['repositories', repoId, 'commits'],
    queryFn: () =>
      customInstance<{ data: Commit[] }>(`/api/v1/repositories/${repoId}/commits?limit=20`),
    enabled: !!repoId,
  });

  const { data: prsResp, isLoading: prsLoading } = useQuery({
    queryKey: ['repositories', repoId, 'pull-requests'],
    queryFn: () =>
      customInstance<{ data: PullRequest[] }>(`/api/v1/repositories/${repoId}/pull-requests?state=all&limit=20`),
    enabled: !!repoId,
  });

  const form = useForm({
    initialValues: { name: '', default_branch: '', owner: '', status: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const repo = resp?.data as RepoData | undefined;
  if (!repo) return <Text>Repository not found</Text>;

  const commits = (commitsResp?.data ?? []) as Commit[];
  const pullRequests = (prsResp?.data ?? []) as PullRequest[];
  const openPRs = pullRequests.filter((pr) => pr.state === 'open');
  const closedPRs = pullRequests.filter((pr) => pr.state !== 'open');

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

      <Tabs defaultValue="commits">
        <Tabs.List>
          <Tabs.Tab value="commits">Commits ({commits.length})</Tabs.Tab>
          <Tabs.Tab value="prs">Pull Requests ({pullRequests.length})</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="commits" pt="sm">
          {commitsLoading ? (
            <Center py="md"><Loader size="sm" /></Center>
          ) : commits.length === 0 ? (
            <Text c="dimmed" py="md">No commits found. Ensure GITHUB_TOKEN is configured.</Text>
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>SHA</Table.Th>
                  <Table.Th>Message</Table.Th>
                  <Table.Th>Author</Table.Th>
                  <Table.Th>Date</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {commits.map((c) => (
                  <Table.Tr key={c.sha}>
                    <Table.Td><Anchor href={`${repo.url}/commit/${c.sha}`} target="_blank" size="sm" ff="monospace">{c.sha.slice(0, 7)}</Anchor></Table.Td>
                    <Table.Td><Text size="sm" lineClamp={1}>{c.message.split('\n')[0]}</Text></Table.Td>
                    <Table.Td><Text size="sm">{c.author}</Text></Table.Td>
                    <Table.Td><Text size="sm">{new Date(c.date).toLocaleDateString()}</Text></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="prs" pt="sm">
          {prsLoading ? (
            <Center py="md"><Loader size="sm" /></Center>
          ) : pullRequests.length === 0 ? (
            <Text c="dimmed" py="md">No pull requests found. Ensure GITHUB_TOKEN is configured.</Text>
          ) : (
            <Tabs defaultValue="open">
              <Tabs.List>
                <Tabs.Tab value="open">Open ({openPRs.length})</Tabs.Tab>
                <Tabs.Tab value="closed">Closed ({closedPRs.length})</Tabs.Tab>
              </Tabs.List>

              {(['open', 'closed'] as const).map((tab) => {
                const prs = tab === 'open' ? openPRs : closedPRs;
                return (
                  <Tabs.Panel key={tab} value={tab} pt="sm">
                    {prs.length === 0 ? (
                      <Text c="dimmed" py="md">No {tab} pull requests.</Text>
                    ) : (
                      <Table striped highlightOnHover>
                        <Table.Thead>
                          <Table.Tr>
                            <Table.Th>#</Table.Th>
                            <Table.Th>Title</Table.Th>
                            <Table.Th>Author</Table.Th>
                            <Table.Th>Branch</Table.Th>
                            <Table.Th>Updated</Table.Th>
                          </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                          {prs.map((pr) => (
                            <Table.Tr key={pr.number}>
                              <Table.Td>
                                <Anchor href={pr.html_url} target="_blank" size="sm">#{pr.number}</Anchor>
                              </Table.Td>
                              <Table.Td><Text size="sm" lineClamp={1}>{pr.title}</Text></Table.Td>
                              <Table.Td><Text size="sm">{pr.author}</Text></Table.Td>
                              <Table.Td>
                                <Text size="sm" ff="monospace">{pr.head_branch} &rarr; {pr.base_branch}</Text>
                              </Table.Td>
                              <Table.Td><Text size="sm">{new Date(pr.updated_at).toLocaleDateString()}</Text></Table.Td>
                            </Table.Tr>
                          ))}
                        </Table.Tbody>
                      </Table>
                    )}
                  </Tabs.Panel>
                );
              })}
            </Tabs>
          )}
        </Tabs.Panel>
      </Tabs>

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
