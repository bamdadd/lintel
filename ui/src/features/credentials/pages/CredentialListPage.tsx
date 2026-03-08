import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useCredentialsListCredentials,
  useCredentialsStoreCredential,
  useCredentialsRevokeCredential,
} from '@/generated/api/credentials/credentials';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';

interface CredItem {
  credential_id: string;
  credential_type: string;
  name: string;
  repo_ids: string[];
  created_at?: string;
  revoked?: boolean;
}

const TYPE_OPTIONS = [
  { value: 'ssh_key', label: 'SSH Key' },
  { value: 'github_token', label: 'GitHub Token' },
  { value: 'api_key', label: 'API Key' },
  { value: 'password', label: 'Password' },
];

const typeColor: Record<string, string> = {
  ssh_key: 'cyan',
  github_token: 'grape',
  api_key: 'blue',
  password: 'orange',
};

export function Component() {
  const { data: resp, isLoading } = useCredentialsListCredentials();
  const storeMut = useCredentialsStoreCredential();
  const revokeMut = useCredentialsRevokeCredential();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [, setSelectedId] = useState<string | null>(null);

  const form = useForm({
    initialValues: {
      name: '',
      credential_type: 'github_token',
      secret: '',
      repo_ids: '',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      secret: (v) => (v.trim() ? null : 'Required'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const credentials = (resp?.data ?? []) as unknown as CredItem[];

  const handleCreate = form.onSubmit((values) => {
    const repoIds = values.repo_ids
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    storeMut.mutate(
      {
        data: {
          name: values.name,
          credential_type: values.credential_type as never,
          secret: values.secret,
          repo_ids: repoIds.length > 0 ? repoIds : undefined,
        },
      },
      {
        onSuccess: () => {
          notifications.show({
            title: 'Created',
            message: 'Credential stored',
            color: 'green',
          });
          void qc.invalidateQueries({ queryKey: ['/api/v1/credentials'] });
          form.reset();
          close();
        },
        onError: () =>
          notifications.show({
            title: 'Error',
            message: 'Failed to store credential',
            color: 'red',
          }),
      },
    );
  });

  const handleRevoke = (id: string) => {
    revokeMut.mutate(
      { credentialId: id },
      {
        onSuccess: () => {
          notifications.show({
            title: 'Revoked',
            message: 'Credential revoked',
            color: 'orange',
          });
          void qc.invalidateQueries({ queryKey: ['/api/v1/credentials'] });
          setSelectedId(null);
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Credentials</Title>
        <Button onClick={open}>Store Credential</Button>
      </Group>

      {credentials.length === 0 ? (
        <EmptyState
          title="No credentials"
          description="Store SSH keys, tokens, and API keys for repository access"
          actionLabel="Store Credential"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Repositories</Table.Th>
              <Table.Th>Created</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {credentials.map((c) => (
              <Table.Tr key={c.credential_id}>
                <Table.Td fw={500}>{c.name}</Table.Td>
                <Table.Td>
                  <Badge
                    color={typeColor[c.credential_type] ?? 'gray'}
                    variant="light"
                    size="sm"
                  >
                    {c.credential_type.replace('_', ' ')}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {c.repo_ids?.length > 0 ? (
                    <Text size="sm" c="dimmed">
                      {c.repo_ids.length} repo{c.repo_ids.length > 1 ? 's' : ''}
                    </Text>
                  ) : (
                    <Text size="sm" c="dimmed">All repos</Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <TimeAgo date={c.created_at} size="sm" c="dimmed" />
                </Table.Td>
                <Table.Td>
                  {c.revoked ? (
                    <Badge color="red" variant="light" size="sm">Revoked</Badge>
                  ) : (
                    <Badge color="green" variant="light" size="sm">Active</Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  {!c.revoked && (
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={() => handleRevoke(c.credential_id)}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Store Credential">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput
              label="Name"
              placeholder="my-github-token"
              {...form.getInputProps('name')}
            />
            <Select
              label="Type"
              data={TYPE_OPTIONS}
              {...form.getInputProps('credential_type')}
            />
            <TextInput
              label="Secret"
              placeholder="ghp_xxxx..."
              type="password"
              {...form.getInputProps('secret')}
            />
            <TextInput
              label="Repository IDs (comma-separated, optional)"
              placeholder="repo-1, repo-2"
              {...form.getInputProps('repo_ids')}
            />
            <Button type="submit" loading={storeMut.isPending}>
              Store
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
