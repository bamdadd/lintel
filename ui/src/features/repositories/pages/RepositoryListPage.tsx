import {
  Title,
  Table,
  Button,
  Group,
  Stack,
  Loader,
  Center,
  Modal,
  TextInput,
  MultiSelect,
  Paper,
  Badge,
  Text,
  ActionIcon,
  Tooltip,
  ThemeIcon,
  Box,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconPlus, IconFolder, IconGitBranch, IconExternalLink,
} from '@tabler/icons-react';
import {
  useRepositoriesListRepositories,
  useRepositoriesRegisterRepository,
  useRepositoriesRemoveRepository,
  getRepositoriesListRepositoriesQueryKey,
} from '@/generated/api/repositories/repositories';
import { useCredentialsListCredentials } from '@/generated/api/credentials/credentials';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EmptyState } from '@/shared/components/EmptyState';
import { useQueryClient } from '@tanstack/react-query';

interface Credential {
  credential_id: string;
  name: string;
  credential_type: string;
}

export function Component() {
  const { data: resp, isLoading } = useRepositoriesListRepositories();
  const { data: credsResp } = useCredentialsListCredentials();
  const registerMutation = useRepositoriesRegisterRepository();
  const deleteMutation = useRepositoriesRemoveRepository();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [opened, { open, close }] = useDisclosure(false);
  const [form, setForm] = useState({ name: '', url: '', credential_ids: [] as string[] });
  const repos = resp?.data;

  const credentials = (credsResp?.data ?? []) as unknown as Credential[];
  const credentialOptions = credentials.map((c) => ({
    value: c.credential_id,
    label: `${c.name} (${c.credential_type})`,
  }));

  const handleCreate = () => {
    registerMutation.mutate(
      { data: { name: form.name, url: form.url } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Registered', message: `Repository "${form.name}" added`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: getRepositoriesListRepositoriesQueryKey() });
          close();
          setForm({ name: '', url: '', credential_ids: [] });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to register repository', color: 'red' });
        },
      },
    );
  };

  const handleDelete = (repoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deleteMutation.mutate(
      { repoId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Repository removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: getRepositoriesListRepositoriesQueryKey() });
        },
      },
    );
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Group gap="xs">
          <Title order={2}>Repositories</Title>
          {repos && repos.length > 0 && (
            <Badge variant="light" size="lg">{repos.length}</Badge>
          )}
        </Group>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>
          Register Repository
        </Button>
      </Group>

      {!repos || repos.length === 0 ? (
        <EmptyState
          title="No repositories yet"
          description="Register your first repository to get started."
          actionLabel="Register Repository"
          onAction={open}
        />
      ) : (
        <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Repository</Table.Th>
                <Table.Th>Branch</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th w={60} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {repos.map((r, i) => (
                <Table.Tr
                  key={i}
                  style={{ cursor: 'pointer' }}
                  onClick={() => void navigate(`/repositories/${String(r.repo_id ?? '')}`)}
                >
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      <ThemeIcon variant="light" color="gray" size="md" radius="md">
                        <IconFolder size={16} />
                      </ThemeIcon>
                      <Box>
                        <Text size="sm" fw={500}>{String(r.name ?? '')}</Text>
                        <Text size="xs" c="dimmed" ff="monospace" truncate>
                          {String(r.url ?? '')}
                        </Text>
                      </Box>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="outline" size="sm" color="gray" leftSection={<IconGitBranch size={10} />}>
                      {String(r.default_branch ?? 'main')}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={String(r.status ?? 'active')} />
                  </Table.Td>
                  <Table.Td>
                    <Tooltip label="Remove repository">
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        size="sm"
                        onClick={(e) => handleDelete(String(r.repo_id ?? ''), e)}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      <Modal opened={opened} onClose={close} title="Register Repository">
        <Stack>
          <TextInput
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <TextInput
            label="URL"
            placeholder="https://github.com/org/repo"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            required
          />
          <MultiSelect
            label="Credentials"
            placeholder="Select credentials for this repository"
            data={credentialOptions}
            value={form.credential_ids}
            onChange={(val) => setForm({ ...form, credential_ids: val })}
            searchable
          />
          <Button onClick={handleCreate} loading={registerMutation.isPending}>
            Register
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
