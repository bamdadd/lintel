import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Textarea,
  Switch,
  Select,
  Loader,
  Center,
  ActionIcon,
  Badge,
  Paper,
  Text,
  Tabs,
  Code,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useSandboxesListSandboxes,
  useSandboxesCreateSandbox,
  useSandboxesDestroySandbox,
} from '@/generated/api/sandboxes/sandboxes';
import { EmptyState } from '@/shared/components/EmptyState';

interface SandboxPreset {
  label: string;
  description: string;
  devcontainer: Record<string, unknown>;
  mounts?: Array<Record<string, string>>;
}

function usePresets() {
  return useQuery<Record<string, SandboxPreset>>({
    queryKey: ['/api/v1/sandboxes/presets'],
    queryFn: async () => {
      const res = await fetch('/api/v1/sandboxes/presets');
      return res.json();
    },
  });
}

const DEFAULT_DEVCONTAINER = JSON.stringify(
  {
    name: 'sandbox',
    image: 'mcr.microsoft.com/devcontainers/base:ubuntu',
    features: [],
    forwardPorts: [],
    postCreateCommand: '',
    postStartCommand: '',
    remoteEnv: {},
    customizations: {},
  },
  null,
  2,
);

interface SandboxEntry {
  sandbox_id: string;
  image: string;
  network_enabled: boolean;
  workspace_id: string;
  channel_id: string;
  devcontainer?: Record<string, unknown>;
}

export function Component() {
  const { data: resp, isLoading } = useSandboxesListSandboxes();
  const { data: presets } = usePresets();
  const createMutation = useSandboxesCreateSandbox();
  const destroyMutation = useSandboxesDestroySandbox();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [selectedSandbox, setSelectedSandbox] = useState<SandboxEntry | null>(null);

  const presetOptions = [
    { value: '', label: 'Custom' },
    ...Object.entries(presets ?? {}).map(([key, p]) => ({
      value: key,
      label: `${p.label}${p.description ? ` — ${p.description}` : ''}`,
    })),
  ];

  const form = useForm({
    initialValues: {
      preset: '',
      workspace_id: 'default',
      channel_id: 'general',
      thread_ts: Date.now().toString(),
      image: 'python:3.12-slim',
      network_enabled: false,
      devcontainer_json: DEFAULT_DEVCONTAINER,
    },
    validate: {
      devcontainer_json: (v) => {
        try {
          JSON.parse(v);
          return null;
        } catch {
          return 'Invalid JSON';
        }
      },
    },
  });

  const handlePresetChange = (value: string | null) => {
    form.setFieldValue('preset', value ?? '');
    if (value && presets?.[value]) {
      const preset = presets[value];
      form.setFieldValue(
        'devcontainer_json',
        JSON.stringify(preset.devcontainer, null, 2),
      );
      form.setFieldValue('image', (preset.devcontainer.image as string) ?? 'python:3.12-slim');
    }
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const sandboxes = (resp?.data ?? []) as SandboxEntry[];

  const handleSubmit = form.onSubmit((values) => {
    const devcontainer = JSON.parse(values.devcontainer_json);
    const features = (devcontainer.features ?? []).map((f: { id: string; options?: Record<string, unknown> }) => ({
      id: f.id,
      options: f.options ?? {},
    }));

    createMutation.mutate(
      {
        data: {
          workspace_id: values.workspace_id,
          channel_id: values.channel_id,
          thread_ts: values.thread_ts,
          image: devcontainer.image ?? values.image,
          network_enabled: values.network_enabled,
          devcontainer: {
            name: devcontainer.name ?? 'sandbox',
            image: devcontainer.image ?? values.image,
            features,
            forward_ports: devcontainer.forwardPorts ?? [],
            post_create_command: devcontainer.postCreateCommand ?? '',
            post_start_command: devcontainer.postStartCommand ?? '',
            remote_env: devcontainer.remoteEnv ?? {},
            customizations: devcontainer.customizations ?? {},
          },
        },
      },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Sandbox created', color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes'] });
          form.reset();
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create sandbox', color: 'red' });
        },
      },
    );
  });

  const handleDestroy = (sandboxId: string) => {
    destroyMutation.mutate(
      { sandboxId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Destroyed', message: 'Sandbox removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes'] });
          if (selectedSandbox?.sandbox_id === sandboxId) setSelectedSandbox(null);
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Sandboxes</Title>
        <Button onClick={open}>Create Sandbox</Button>
      </Group>

      {sandboxes.length === 0 && !selectedSandbox ? (
        <EmptyState
          title="No sandboxes"
          description="Create a sandbox with a devcontainer configuration"
          actionLabel="Create Sandbox"
          onAction={open}
        />
      ) : (
        <Group align="flex-start" gap="md" grow>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Image</Table.Th>
                <Table.Th>Features</Table.Th>
                <Table.Th>Network</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sandboxes.map((s) => (
                <Table.Tr
                  key={s.sandbox_id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedSandbox(s)}
                  bg={selectedSandbox?.sandbox_id === s.sandbox_id ? 'var(--mantine-color-dark-5)' : undefined}
                >
                  <Table.Td><Code>{s.sandbox_id.slice(0, 12)}</Code></Table.Td>
                  <Table.Td>{s.devcontainer?.image as string ?? s.image}</Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="wrap">
                      {((s.devcontainer?.features as Array<{ id: string }>) ?? []).map((f) => {
                        const short = f.id.split('/').pop()?.replace(/:.*$/, '') ?? f.id;
                        return <Badge key={f.id} size="xs" variant="light">{short}</Badge>;
                      })}
                      {((s.devcontainer?.features as Array<{ id: string }>) ?? []).length === 0 && <Text size="xs" c="dimmed">—</Text>}
                    </Group>
                  </Table.Td>
                  <Table.Td><Badge color={s.network_enabled ? 'green' : 'gray'}>{s.network_enabled ? 'on' : 'off'}</Badge></Table.Td>
                  <Table.Td>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDestroy(s.sandbox_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          {selectedSandbox?.devcontainer && (
            <Paper withBorder p="md" radius="md" maw={500}>
              <Title order={5} mb="sm">devcontainer.json</Title>
              <Code block style={{ fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                {JSON.stringify(selectedSandbox.devcontainer, null, 2)}
              </Code>
            </Paper>
          )}
        </Group>
      )}

      <Modal opened={opened} onClose={close} title="Create Sandbox" size="lg">
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <Select
              label="Preset"
              description="Choose a preset or customise the devcontainer config below"
              data={presetOptions}
              value={form.values.preset}
              onChange={handlePresetChange}
              searchable
            />
            <Tabs defaultValue="devcontainer">
              <Tabs.List>
                <Tabs.Tab value="devcontainer">devcontainer.json</Tabs.Tab>
                <Tabs.Tab value="basic">Basic</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="devcontainer" pt="md">
                <Textarea
                  label="devcontainer.json"
                  description="Define the sandbox environment using the devcontainer format"
                  autosize
                  minRows={16}
                  maxRows={30}
                  styles={{ input: { fontFamily: 'monospace', fontSize: 12 } }}
                  {...form.getInputProps('devcontainer_json')}
                />
              </Tabs.Panel>

              <Tabs.Panel value="basic" pt="md">
                <Stack gap="sm">
                  <TextInput label="Workspace ID" {...form.getInputProps('workspace_id')} />
                  <TextInput label="Channel ID" {...form.getInputProps('channel_id')} />
                  <Switch
                    label="Network Enabled"
                    {...form.getInputProps('network_enabled', { type: 'checkbox' })}
                  />
                </Stack>
              </Tabs.Panel>
            </Tabs>
            <Button type="submit" loading={createMutation.isPending}>Create Sandbox</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
