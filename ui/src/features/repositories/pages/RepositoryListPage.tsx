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
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';
import {
  useRepositoriesListRepositories,
  useRepositoriesRegisterRepository,
  useRepositoriesRemoveRepository,
  getRepositoriesListRepositoriesQueryKey,
} from '@/generated/api/repositories/repositories';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EmptyState } from '@/shared/components/EmptyState';
import { useQueryClient } from '@tanstack/react-query';

export function Component() {
  const { data: resp, isLoading } = useRepositoriesListRepositories();
  const registerMutation = useRepositoriesRegisterRepository();
  const deleteMutation = useRepositoriesRemoveRepository();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [form, setForm] = useState({ repo_id: '', name: '', url: '' });
  const repos = resp?.data;

  const handleCreate = () => {
    registerMutation.mutate(
      { data: form },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: getRepositoriesListRepositoriesQueryKey() });
          close();
          setForm({ repo_id: '', name: '', url: '' });
        },
      },
    );
  };

  const handleDelete = (repoId: string) => {
    deleteMutation.mutate(
      { repoId },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: getRepositoriesListRepositoriesQueryKey() });
        },
      },
    );
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Repositories</Title>
        <Button onClick={open}>Register Repository</Button>
      </Group>

      {!repos || repos.length === 0 ? (
        <EmptyState
          title="No repositories yet"
          description="Register your first repository to get started."
          actionLabel="Register Repository"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>URL</Table.Th>
              <Table.Th>Branch</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {repos.map((r, i) => (
              <Table.Tr key={i}>
                <Table.Td>{String(r.repo_id ?? '')}</Table.Td>
                <Table.Td>{String(r.name ?? '')}</Table.Td>
                <Table.Td>{String(r.url ?? '')}</Table.Td>
                <Table.Td>{String(r.default_branch ?? 'main')}</Table.Td>
                <Table.Td>
                  <StatusBadge status={String(r.status ?? 'active')} />
                </Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    color="red"
                    variant="subtle"
                    onClick={() => handleDelete(String(r.repo_id ?? ''))}
                  >
                    Delete
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Register Repository">
        <Stack>
          <TextInput
            label="Repository ID"
            value={form.repo_id}
            onChange={(e) => setForm({ ...form, repo_id: e.target.value })}
            required
          />
          <TextInput
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <TextInput
            label="URL"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            required
          />
          <Button onClick={handleCreate} loading={registerMutation.isPending}>
            Register
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
