import {
  Title,
  Stack,
  Tabs,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Textarea,
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
import type { CredentialType } from '@/generated/models/credentialType';
import { EmptyState } from '@/shared/components/EmptyState';

interface Credential {
  credential_id: string;
  credential_type: string;
  name: string;
}

export function Component() {
  const { data: resp, isLoading } = useCredentialsListCredentials();
  const storeMutation = useCredentialsStoreCredential();
  const revokeMutation = useCredentialsRevokeCredential();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      name: '',
      credential_type: 'github_token',
      secret: '',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      secret: (v) => (v.trim() ? null : 'Required'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const credentials = (resp?.data ?? []) as unknown as Credential[];
  const isSSHKey = form.values.credential_type === 'ssh_key';

  const handleSubmit = form.onSubmit((values) => {
    storeMutation.mutate(
      {
        data: {
          name: values.name,
          credential_type: values.credential_type as CredentialType,
          secret: values.secret,
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
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {credentials.map((c) => (
                    <Table.Tr key={c.credential_id}>
                      <Table.Td>{c.name}</Table.Td>
                      <Table.Td>{c.credential_type}</Table.Td>
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
            <TextInput label="Name" placeholder="My GitHub Token" {...form.getInputProps('name')} />
            <Select
              label="Type"
              data={[
                { value: 'github_token', label: 'GitHub Token' },
                { value: 'ssh_key', label: 'SSH Key' },
                { value: 'api_key', label: 'API Key' },
              ]}
              {...form.getInputProps('credential_type')}
            />
            {isSSHKey ? (
              <Textarea
                label="SSH Private Key"
                placeholder={"-----BEGIN OPENSSH PRIVATE KEY-----\n..."}
                autosize
                minRows={8}
                styles={{ input: { fontFamily: 'monospace', fontSize: 12 } }}
                {...form.getInputProps('secret')}
              />
            ) : (
              <PasswordInput
                label={form.values.credential_type === 'github_token' ? 'Token' : 'API Key'}
                placeholder={form.values.credential_type === 'github_token' ? 'ghp_...' : 'sk-...'}
                {...form.getInputProps('secret')}
              />
            )}
            <Button type="submit" loading={storeMutation.isPending}>Store</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
