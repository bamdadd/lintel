import {
  Title,
  Stack,
  Tabs,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Select,
  Loader,
  Center,
  ActionIcon,
  Text,
  PasswordInput,
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

interface Credential {
  credential_id: string;
  credential_type: string;
  name: string;
  repo_ids: string[];
}

export function Component() {
  const { data: resp, isLoading } = useCredentialsListCredentials();
  const storeMutation = useCredentialsStoreCredential();
  const revokeMutation = useCredentialsRevokeCredential();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      credential_id: '',
      name: '',
      credential_type: 'github_token',
      secret: '',
      repo_ids: '',
    },
    validate: {
      credential_id: (v) => (v.trim() ? null : 'Required'),
      name: (v) => (v.trim() ? null : 'Required'),
      secret: (v) => (v.trim() ? null : 'Required'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const credentials = (resp?.data ?? []) as Credential[];

  const handleSubmit = form.onSubmit((values) => {
    storeMutation.mutate(
      {
        data: {
          credential_id: values.credential_id,
          name: values.name,
          credential_type: values.credential_type as 'github_token' | 'ssh_key' | 'api_key',
          secret: values.secret,
          repo_ids: values.repo_ids ? values.repo_ids.split(',').map((s) => s.trim()) : [],
        },
      },
      {
        onSuccess: () => {
          notifications.show({ title: 'Stored', message: `Credential "${values.name}" saved`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/credentials'] });
          form.reset();
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to store credential', color: 'red' });
        },
      },
    );
  });

  const handleRevoke = (credentialId: string) => {
    revokeMutation.mutate(
      { credentialId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Revoked', message: 'Credential removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/credentials'] });
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Title order={2}>Security</Title>
      <Tabs defaultValue="credentials">
        <Tabs.List>
          <Tabs.Tab value="credentials">Credentials</Tabs.Tab>
          <Tabs.Tab value="pii">PII Detection</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="credentials" pt="md">
          <Stack gap="md">
            <Group justify="flex-end">
              <Button onClick={open}>Add Credential</Button>
            </Group>
            {credentials.length === 0 ? (
              <EmptyState
                title="No credentials"
                description="Store credentials to connect to repositories and services"
                actionLabel="Add Credential"
                onAction={open}
              />
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>ID</Table.Th>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th>Repos</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {credentials.map((c) => (
                    <Table.Tr key={c.credential_id}>
                      <Table.Td>{c.credential_id}</Table.Td>
                      <Table.Td>{c.name}</Table.Td>
                      <Table.Td>{c.credential_type}</Table.Td>
                      <Table.Td><Text size="sm">{c.repo_ids?.join(', ') || '—'}</Text></Table.Td>
                      <Table.Td>
                        <ActionIcon color="red" variant="subtle" onClick={() => handleRevoke(c.credential_id)}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="pii" pt="md">
          <Text c="dimmed">PII detection and vault activity monitoring.</Text>
        </Tabs.Panel>
      </Tabs>

      <Modal opened={opened} onClose={close} title="Add Credential">
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <TextInput label="Credential ID" placeholder="gh-token-1" {...form.getInputProps('credential_id')} />
            <TextInput label="Name" placeholder="GitHub Token" {...form.getInputProps('name')} />
            <Select
              label="Type"
              data={[
                { value: 'github_token', label: 'GitHub Token' },
                { value: 'ssh_key', label: 'SSH Key' },
                { value: 'api_key', label: 'API Key' },
              ]}
              {...form.getInputProps('credential_type')}
            />
            <PasswordInput label="Secret" placeholder="ghp_..." {...form.getInputProps('secret')} />
            <TextInput
              label="Repository IDs"
              placeholder="repo-1, repo-2 (comma separated)"
              {...form.getInputProps('repo_ids')}
            />
            <Button type="submit" loading={storeMutation.isPending}>Store</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
