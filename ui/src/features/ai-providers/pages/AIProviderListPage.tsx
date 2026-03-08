import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch, PasswordInput,
  Textarea,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconKey } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useAiProvidersListAiProviders,
  useAiProvidersCreateAiProvider,
  useAiProvidersUpdateAiProvider,
  useAiProvidersDeleteAiProvider,
  useAiProvidersUpdateApiKey,
} from '@/generated/api/ai-providers/ai-providers';
import { EmptyState } from '@/shared/components/EmptyState';

interface ProviderItem {
  provider_id: string;
  provider_type: string;
  name: string;
  api_base: string;
  is_default: boolean;
  has_api_key: boolean;
  config: Record<string, unknown>;
}

const PROVIDER_TYPES = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'azure_openai', label: 'Azure OpenAI' },
  { value: 'google', label: 'Google' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'bedrock', label: 'AWS Bedrock' },
  { value: 'custom', label: 'Custom' },
];

const typeColor: Record<string, string> = {
  anthropic: 'violet', openai: 'green', azure_openai: 'blue', google: 'red', ollama: 'gray', bedrock: 'orange', custom: 'cyan',
};

const FIELD_CONFIG: Record<string, { showApiKey: boolean; showApiBase: boolean; apiKeyRequired: boolean; apiBaseRequired: boolean }> = {
  anthropic:    { showApiKey: true,  showApiBase: true,  apiKeyRequired: true,  apiBaseRequired: false },
  openai:       { showApiKey: true,  showApiBase: true,  apiKeyRequired: true,  apiBaseRequired: false },
  azure_openai: { showApiKey: true,  showApiBase: true,  apiKeyRequired: true,  apiBaseRequired: true },
  google:       { showApiKey: true,  showApiBase: true,  apiKeyRequired: true,  apiBaseRequired: false },
  ollama:       { showApiKey: false, showApiBase: true,  apiKeyRequired: false, apiBaseRequired: true },
  bedrock:      { showApiKey: false, showApiBase: true,  apiKeyRequired: false, apiBaseRequired: false },
  custom:       { showApiKey: true,  showApiBase: true,  apiKeyRequired: false, apiBaseRequired: true },
};

export function Component() {
  const { data: resp, isLoading } = useAiProvidersListAiProviders();
  const createMut = useAiProvidersCreateAiProvider();
  const updateMut = useAiProvidersUpdateAiProvider();
  const deleteMut = useAiProvidersDeleteAiProvider();
  const apiKeyMut = useAiProvidersUpdateApiKey();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<ProviderItem | null>(null);
  const [keyModal, setKeyModal] = useState<string | null>(null);
  const [newKey, setNewKey] = useState('');

  const form = useForm({
    initialValues: {
      provider_type: 'anthropic',
      name: '',
      api_key: '',
      api_base: '',
      is_default: false,
      config: '',
      aws_region: '',
      aws_profile: '',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      api_key: (v, values) => {
        const cfg = FIELD_CONFIG[values.provider_type];
        return cfg?.apiKeyRequired && !v.trim() ? 'API key is required for this provider' : null;
      },
      api_base: (v, values) => {
        const cfg = FIELD_CONFIG[values.provider_type];
        return cfg?.apiBaseRequired && !v.trim() ? 'API base URL is required for this provider' : null;
      },
    },
  });

  const fieldCfg = FIELD_CONFIG[form.values.provider_type] ?? { showApiKey: true, showApiBase: true, apiKeyRequired: false, apiBaseRequired: false };

  const editFormState = useForm({
    initialValues: {
      name: '',
      api_base: '',
      is_default: false,
      config: '',
      aws_region: '',
      aws_profile: '',
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const providers = (resp?.data ?? []) as ProviderItem[];

  const handleCreate = form.onSubmit((values) => {
    let config: Record<string, unknown> = {};
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON config', color: 'red' }); return; }
    }
    if (values.provider_type === 'bedrock') {
      if (values.aws_region.trim()) config.aws_region_name = values.aws_region.trim();
      if (values.aws_profile.trim()) config.aws_profile_name = values.aws_profile.trim();
    }
    const { aws_region: _r, aws_profile: _p, ...rest } = values;
    createMut.mutate(
      { data: { ...rest, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'AI Provider added', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/ai-providers'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
      },
    );
  });

  const openEdit = (p: ProviderItem) => {
    setEditItem(p);
    const cfg = p.config ?? {};
    editFormState.setValues({
      name: p.name,
      api_base: p.api_base ?? '',
      is_default: p.is_default,
      config: p.config ? JSON.stringify(p.config, null, 2) : '',
      aws_region: (cfg.aws_region_name as string) ?? '',
      aws_profile: (cfg.aws_profile_name as string) ?? '',
    });
  };

  const handleEdit = editFormState.onSubmit((values) => {
    if (!editItem) return;
    let config: Record<string, unknown> | undefined;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON', color: 'red' }); return; }
    }
    if (editItem.provider_type === 'bedrock') {
      config = config ?? {};
      if (values.aws_region.trim()) config.aws_region_name = values.aws_region.trim();
      else delete config.aws_region_name;
      if (values.aws_profile.trim()) config.aws_profile_name = values.aws_profile.trim();
      else delete config.aws_profile_name;
    }
    const { aws_region: _r, aws_profile: _p, ...rest } = values;
    updateMut.mutate(
      { providerId: editItem.provider_id, data: { ...rest, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Provider updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/ai-providers'] });
          setEditItem(null);
        },
      },
    );
  });

  const handleUpdateKey = () => {
    if (!keyModal || !newKey.trim()) return;
    apiKeyMut.mutate(
      { providerId: keyModal, data: { api_key: newKey } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'API key updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/ai-providers'] });
          setKeyModal(null); setNewKey('');
        },
      },
    );
  };

  const handleDelete = (id: string) => {
    deleteMut.mutate({ providerId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Provider removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/ai-providers'] });
        if (editItem?.provider_id === id) setEditItem(null);
      },
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>AI Providers</Title>
        <Button onClick={open}>Add Provider</Button>
      </Group>

      {providers.length === 0 ? (
        <EmptyState title="No AI providers" description="Configure LLM providers for your agents" actionLabel="Add Provider" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>API Key</Table.Th>
              <Table.Th>Default</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {providers.map((p) => (
              <Table.Tr key={p.provider_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(p)}>
                <Table.Td>{p.name}</Table.Td>
                <Table.Td><Badge color={typeColor[p.provider_type] ?? 'gray'}>{p.provider_type}</Badge></Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <Badge color={p.has_api_key ? 'green' : 'gray'} variant="light">{p.has_api_key ? 'Set' : 'Missing'}</Badge>
                    <ActionIcon size="sm" variant="subtle" onClick={(e) => { e.stopPropagation(); setKeyModal(p.provider_id); }}>
                      <IconKey size={14} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
                <Table.Td>{p.is_default && <Badge color="blue">Default</Badge>}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(p.provider_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Add AI Provider" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My Anthropic Account" {...form.getInputProps('name')} />
            <Select label="Provider Type" data={PROVIDER_TYPES} {...form.getInputProps('provider_type')} />
            {fieldCfg.showApiKey && (
              <PasswordInput
                label={`API Key${fieldCfg.apiKeyRequired ? '' : ' (optional)'}`}
                placeholder="sk-..."
                {...form.getInputProps('api_key')}
              />
            )}
            {fieldCfg.showApiBase && (
              <TextInput
                label={`API Base URL${fieldCfg.apiBaseRequired ? '' : ' (optional)'}`}
                placeholder={form.values.provider_type === 'ollama' ? 'http://localhost:11434' : 'https://api.example.com'}
                {...form.getInputProps('api_base')}
              />
            )}
            {form.values.provider_type === 'bedrock' && (
              <>
                <TextInput label="AWS Region" placeholder="eu-west-1" {...form.getInputProps('aws_region')} />
                <TextInput label="AWS Profile (optional)" placeholder="default" description="AWS SSO/CLI profile name" {...form.getInputProps('aws_profile')} />
              </>
            )}
            <Switch label="Set as default provider" {...form.getInputProps('is_default', { type: 'checkbox' })} />
            <Textarea label="Extra Config (JSON)" minRows={2} styles={{ input: { fontFamily: 'monospace' } }} {...form.getInputProps('config')} />
            <Button type="submit" loading={createMut.isPending}>Add Provider</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editFormState.getInputProps('name')} />
            <TextInput label="API Base URL" {...editFormState.getInputProps('api_base')} />
            {editItem?.provider_type === 'bedrock' && (
              <>
                <TextInput label="AWS Region" placeholder="eu-west-1" {...editFormState.getInputProps('aws_region')} />
                <TextInput label="AWS Profile (optional)" placeholder="default" description="AWS SSO/CLI profile name" {...editFormState.getInputProps('aws_profile')} />
              </>
            )}
            <Switch label="Default provider" {...editFormState.getInputProps('is_default', { type: 'checkbox' })} />
            <Textarea label="Config (JSON)" minRows={2} styles={{ input: { fontFamily: 'monospace' } }} {...editFormState.getInputProps('config')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!keyModal} onClose={() => { setKeyModal(null); setNewKey(''); }} title="Update API Key">
        <Stack gap="sm">
          <PasswordInput label="New API Key" value={newKey} onChange={(e) => setNewKey(e.currentTarget.value)} placeholder="sk-..." />
          <Button onClick={handleUpdateKey} loading={apiKeyMut.isPending}>Update Key</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
