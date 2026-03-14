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
  NumberInput,
  Progress,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconTrashX } from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  useSandboxesListSandboxes,
  useSandboxesCreateSandbox,
  useSandboxesDestroySandbox,
  useSandboxesGetSandboxStatus,
} from '@/generated/api/sandboxes/sandboxes';
import { useSettingsGetSettings } from '@/generated/api/settings/settings';
import { EmptyState } from '@/shared/components/EmptyState';
import { getStatusColor } from '@/shared/components/StatusBadge';

function SandboxStatusBadge({ sandboxId }: { sandboxId: string }) {
  const { data } = useSandboxesGetSandboxStatus(sandboxId, {
    query: { refetchInterval: 5000 },
  });
  const status = (data?.data as { status?: string } | undefined)?.status ?? 'unknown';
  return <Badge size="sm" color={getStatusColor(status)}>{status}</Badge>;
}

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
    image: 'lintel-sandbox:latest',
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

interface MountEntry {
  source: string;
  target: string;
  type: string;
}

interface SandboxEntry {
  sandbox_id: string;
  image: string;
  network_enabled: boolean;
  workspace_id: string;
  channel_id: string;
  pipeline_id?: string;
  devcontainer?: Record<string, unknown>;
  mounts?: MountEntry[];
}

export function Component() {
  const { data: resp, isLoading } = useSandboxesListSandboxes({ query: { refetchInterval: 5000 } });
  const { data: settingsResp } = useSettingsGetSettings();
  const maxSandboxes = (settingsResp?.data as { max_sandboxes?: number } | undefined)?.max_sandboxes ?? 20;
  const { data: presets } = usePresets();
  const createMutation = useSandboxesCreateSandbox();
  const destroyMutation = useSandboxesDestroySandbox();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const navigate = useNavigate();
  const [selectedSandbox, setSelectedSandbox] = useState<SandboxEntry | null>(null);

  const presetOptions = [
    { value: '', label: 'Custom' },
    ...Object.entries(presets ?? {}).map(([key, p]) => ({
      value: key,
      label: `${p.label}${p.description ? ` — ${p.description}` : ''}`,
    })),
  ];

  const [batchProgress, setBatchProgress] = useState<{ total: number; done: number; failed: number } | null>(null);

  const form = useForm({
    initialValues: {
      preset: '',
      workspace_id: 'default',
      channel_id: 'general',
      thread_ts: Date.now().toString(),
      image: 'python:3.12-slim',
      network_enabled: false,
      devcontainer_json: DEFAULT_DEVCONTAINER,
      count: 1,
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

  const sandboxes = ((resp?.data ?? []) as unknown as SandboxEntry[]).filter((s) => s.sandbox_id);

  const handleSubmit = form.onSubmit((values) => {
    const devcontainer = JSON.parse(values.devcontainer_json);
    const features = (devcontainer.features ?? []).map((f: { id: string; options?: Record<string, unknown> }) => ({
      id: f.id,
      options: f.options ?? {},
    }));

    const count = Math.max(1, Math.min(values.count, 50));
    const progress = { total: count, done: 0, failed: 0 };
    setBatchProgress({ ...progress });

    const createOne = () => {
      const data = {
        workspace_id: values.workspace_id,
        channel_id: values.channel_id,
        thread_ts: `${Date.now()}`,
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
      };
      return new Promise<void>((resolve) => {
        createMutation.mutate(
          { data },
          {
            onSuccess: () => {
              progress.done++;
              setBatchProgress({ ...progress });
              resolve();
            },
            onError: () => {
              progress.failed++;
              setBatchProgress({ ...progress });
              resolve();
            },
          },
        );
      });
    };

    const runBatch = async () => {
      for (let i = 0; i < count; i++) {
        await createOne();
      }
      void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes'] });
      const msg = progress.failed > 0
        ? `Created ${progress.done}, failed ${progress.failed}`
        : `Created ${progress.done} sandbox${progress.done > 1 ? 'es' : ''}`;
      notifications.show({
        title: progress.failed > 0 ? 'Partial Success' : 'Created',
        message: msg,
        color: progress.failed > 0 ? 'yellow' : 'green',
      });
      setBatchProgress(null);
      form.reset();
      close();
    };
    void runBatch();
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
        <Group gap="sm" align="baseline">
          <Title order={2}>Sandboxes</Title>
          <Badge
            size="lg"
            variant="light"
            color={sandboxes.length >= maxSandboxes ? 'red' : sandboxes.length >= maxSandboxes * 0.8 ? 'yellow' : 'blue'}
          >
            {sandboxes.length} / {maxSandboxes}
          </Badge>
        </Group>
        <Group gap="xs">
          {sandboxes.length > 0 && (
            <Button
              variant="light"
              color="red"
              leftSection={<IconTrashX size={16} />}
              onClick={() => {
                const ids = sandboxes.map((s) => s.sandbox_id);
                let completed = 0;
                for (const id of ids) {
                  destroyMutation.mutate(
                    { sandboxId: id },
                    {
                      onSuccess: () => {
                        completed++;
                        if (completed === ids.length) {
                          notifications.show({ title: 'Destroyed', message: `Removed ${ids.length} sandboxes`, color: 'orange' });
                          void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes'] });
                          setSelectedSandbox(null);
                        }
                      },
                    },
                  );
                }
              }}
            >
              Destroy All
            </Button>
          )}
          <Button onClick={open}>Create Sandbox</Button>
        </Group>
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
                <Table.Th>Status</Table.Th>
                <Table.Th>Allocated To</Table.Th>
                <Table.Th>Image</Table.Th>
                <Table.Th>Network</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sandboxes.map((s) => (
                <Table.Tr
                  key={s.sandbox_id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/sandboxes/${s.sandbox_id}`)}
                  bg={selectedSandbox?.sandbox_id === s.sandbox_id ? 'var(--mantine-color-dark-5)' : undefined}
                >
                  <Table.Td><Code>{s.sandbox_id.slice(0, 12)}</Code></Table.Td>
                  <Table.Td><SandboxStatusBadge sandboxId={s.sandbox_id} /></Table.Td>
                  <Table.Td>
                    {s.pipeline_id ? (
                      <Badge
                        size="sm"
                        variant="light"
                        color="blue"
                        style={{ cursor: 'pointer' }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/pipelines/${s.pipeline_id}`); }}
                      >
                        {s.pipeline_id.slice(0, 8)}…
                      </Badge>
                    ) : (
                      <Badge size="sm" variant="light" color="green">free</Badge>
                    )}
                  </Table.Td>
                  <Table.Td><Text size="xs">{s.devcontainer?.image as string ?? s.image}</Text></Table.Td>
                  <Table.Td><Badge color={s.network_enabled ? 'green' : 'gray'} size="sm">{s.network_enabled ? 'on' : 'off'}</Badge></Table.Td>
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
            {form.values.preset && presets?.[form.values.preset]?.mounts && (
              <Paper withBorder p="xs" radius="md" bg="dark.8">
                <Text size="xs" fw={600} mb={4}>Mounts (from preset)</Text>
                {presets[form.values.preset]?.mounts?.map((m) => (
                  <Group key={m.target} gap="xs">
                    <Badge size="xs" variant="light" color="violet">{m.type}</Badge>
                    <Text size="xs" ff="monospace" c="dimmed">{m.source}</Text>
                    <Text size="xs" c="dimmed">→</Text>
                    <Text size="xs" ff="monospace">{m.target}</Text>
                  </Group>
                ))}
              </Paper>
            )}
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
            <NumberInput
              label="Count"
              description="Number of sandboxes to create"
              min={1}
              max={50}
              {...form.getInputProps('count')}
            />
            {batchProgress && (
              <Stack gap={4}>
                <Text size="xs" c="dimmed">
                  Creating {batchProgress.done + batchProgress.failed} / {batchProgress.total}
                  {batchProgress.failed > 0 && ` (${batchProgress.failed} failed)`}
                </Text>
                <Progress
                  value={((batchProgress.done + batchProgress.failed) / batchProgress.total) * 100}
                  color={batchProgress.failed > 0 ? 'yellow' : 'blue'}
                  animated
                />
              </Stack>
            )}
            <Button type="submit" loading={!!batchProgress}>
              Create {form.values.count > 1 ? `${form.values.count} Sandboxes` : 'Sandbox'}
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
