import { useState, useEffect } from 'react';
import {
  Title,
  Stack,
  SimpleGrid,
  Center,
  Loader,
  Tabs,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Select,
  ActionIcon,
  Badge,
  Text,
  MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconRobot, IconPlug } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';
import { useAgentsListAgentDefinitions } from '@/generated/api/agents/agents';
import { SlackConnectionCard } from './SlackConnectionCard';
import { TelegramConnectionCard } from './TelegramConnectionCard';
import { listChannelConnections, disconnectSlack, disconnectTelegram } from './channelsApi';
import type { ChannelConnection } from './channelsApi';
import { EmptyState } from '@/shared/components/EmptyState';

// --- Bot types & hooks ---

interface Bot {
  bot_id: string;
  name: string;
  platform: string;
  project_ids: string[];
  workflow_ids: string[];
  agent_ids: string[];
  scopes: string[];
  status: string;
}

interface CreateBotPayload {
  name: string;
  platform: string;
  project_ids: string[];
  workflow_ids: string[];
  agent_ids: string[];
}

interface UpdateBotPayload {
  name?: string;
  platform?: string;
  project_ids?: string[];
  workflow_ids?: string[];
  agent_ids?: string[];
  status?: string;
}

type ListResponse = { data: Bot[]; status: number };
type ItemResponse = { data: Bot; status: number };

const BOT_QUERY_KEY = ['/api/v1/bots'];

const PLATFORMS = [
  { value: 'slack', label: 'Slack' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'discord', label: 'Discord' },
  { value: 'custom', label: 'Custom' },
];

const STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'suspended', label: 'Suspended' },
];

function statusColor(status: string): string {
  switch (status) {
    case 'active': return 'green';
    case 'inactive': return 'gray';
    case 'suspended': return 'red';
    default: return 'gray';
  }
}

function useBots() {
  return useQuery<ListResponse>({
    queryKey: BOT_QUERY_KEY,
    queryFn: () => customInstance<ListResponse>('/api/v1/bots', { method: 'GET' }),
  });
}

function useCreateBot() {
  return useMutation<ItemResponse, Error, CreateBotPayload>({
    mutationFn: (data) =>
      customInstance<ItemResponse>('/api/v1/bots', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  });
}

function useUpdateBot() {
  return useMutation<ItemResponse, Error, { botId: string; data: UpdateBotPayload }>({
    mutationFn: ({ botId, data }) =>
      customInstance<ItemResponse>(`/api/v1/bots/${botId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  });
}

function useDeleteBot() {
  return useMutation<unknown, Error, string>({
    mutationFn: (botId) =>
      customInstance<unknown>(`/api/v1/bots/${botId}`, { method: 'DELETE' }),
  });
}

// --- Bots Tab ---

function BotsTab() {
  const { data: resp, isLoading } = useBots();
  const createMutation = useCreateBot();
  const updateMutation = useUpdateBot();
  const deleteMutation = useDeleteBot();
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [detailBot, setDetailBot] = useState<Bot | null>(null);

  const { data: projectsResp } = useProjectsListProjects();
  const projectsRaw = projectsResp?.data ?? projectsResp ?? [];
  const projects = (Array.isArray(projectsRaw) ? projectsRaw : []) as Array<{ project_id: string; name: string }>;
  const { data: wfResp } = useWorkflowDefinitionsListWorkflowDefinitions();
  const wfRaw = wfResp?.data ?? wfResp ?? [];
  const workflows = (Array.isArray(wfRaw) ? wfRaw : []) as Array<{ name: string }>;
  const { data: agentResp } = useAgentsListAgentDefinitions();
  const agentRaw = agentResp?.data ?? agentResp ?? [];
  const agents = (Array.isArray(agentRaw) ? agentRaw : []) as Array<{ agent_id: string; name: string; role: string }>;

  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));
  const workflowOptions = workflows.map((w) => ({ value: w.name, label: w.name }));
  // Deduplicate agents by role
  const seenRoles = new Set<string>();
  const agentOptions = agents.reduce<Array<{ value: string; label: string }>>((acc, a) => {
    const key = a.role ?? a.agent_id;
    if (!seenRoles.has(key)) {
      seenRoles.add(key);
      acc.push({ value: key, label: a.name ?? key });
    }
    return acc;
  }, []);

  const createForm = useForm({
    initialValues: { name: '', platform: 'slack', project_ids: [] as string[], workflow_ids: [] as string[], agent_ids: [] as string[] },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: { name: '', platform: 'custom', project_ids: [] as string[], workflow_ids: [] as string[], agent_ids: [] as string[], status: 'active' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const bots = resp?.data ?? [];

  const handleCreate = createForm.onSubmit((values) => {
    createMutation.mutate(values, {
      onSuccess: () => {
        notifications.show({ title: 'Created', message: `Bot "${values.name}" created`, color: 'green' });
        void queryClient.invalidateQueries({ queryKey: BOT_QUERY_KEY });
        createForm.reset();
        closeCreate();
      },
      onError: () => {
        notifications.show({ title: 'Error', message: 'Failed to create bot', color: 'red' });
      },
    });
  });

  const openDetail = (bot: Bot) => {
    setDetailBot(bot);
    editForm.setValues({
      name: bot.name ?? '',
      platform: bot.platform ?? 'custom',
      project_ids: (bot.project_ids ?? []).filter(Boolean),
      workflow_ids: (bot.workflow_ids ?? []).filter(Boolean),
      agent_ids: (bot.agent_ids ?? []).filter(Boolean),
      status: bot.status ?? 'active',
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!detailBot) return;
    updateMutation.mutate(
      { botId: detailBot.bot_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: `Bot "${values.name}" updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: BOT_QUERY_KEY });
          setDetailBot(null);
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update bot', color: 'red' });
        },
      },
    );
  });

  const handleDelete = (botId: string) => {
    deleteMutation.mutate(botId, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Bot removed', color: 'orange' });
        void queryClient.invalidateQueries({ queryKey: BOT_QUERY_KEY });
        if (detailBot?.bot_id === botId) setDetailBot(null);
      },
    });
  };

  return (
    <>
      <Group justify="flex-end" mb="sm">
        <Button onClick={openCreate}>Add Bot</Button>
      </Group>

      {bots.length === 0 ? (
        <EmptyState
          title="No bots registered"
          description="Register bots to connect messaging platforms like Slack and Telegram"
          actionLabel="Add Bot"
          onAction={openCreate}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Platform</Table.Th>
              <Table.Th>Projects</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {bots.map((b) => (
              <Table.Tr key={b.bot_id} style={{ cursor: 'pointer' }} onClick={() => openDetail(b)}>
                <Table.Td>{b.name ?? 'Unnamed'}</Table.Td>
                <Table.Td><Badge variant="light">{b.platform ?? 'unknown'}</Badge></Table.Td>
                <Table.Td>
                  {(b.project_ids ?? []).length > 0
                    ? b.project_ids.map((pid) => {
                        const p = projects.find((pr) => pr.project_id === pid);
                        return <Badge key={pid} variant="outline" size="sm" mr={4}>{p?.name ?? pid}</Badge>;
                      })
                    : <Text size="sm" c="dimmed">all projects</Text>}
                </Table.Td>
                <Table.Td><Badge color={statusColor(b.status ?? 'inactive')}>{b.status ?? 'unknown'}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    onClick={(e) => { e.stopPropagation(); handleDelete(b.bot_id); }}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={createOpened} onClose={closeCreate} title="Add Bot" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My Slack Bot" {...createForm.getInputProps('name')} />
            <Select label="Platform" data={PLATFORMS} {...createForm.getInputProps('platform')} />
            <MultiSelect label="Projects" description="Which projects this bot can access (empty = all)" data={projectOptions} {...createForm.getInputProps('project_ids')} searchable clearable />
            <MultiSelect label="Workflows" description="Which workflows this bot can trigger (empty = all)" data={workflowOptions} {...createForm.getInputProps('workflow_ids')} searchable clearable />
            <MultiSelect label="Agent Roles" description="Which agent roles this bot can use (empty = all)" data={agentOptions} {...createForm.getInputProps('agent_ids')} searchable clearable />
            <Button type="submit" loading={createMutation.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!detailBot} onClose={() => setDetailBot(null)} title={`Bot: ${detailBot?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Select label="Platform" data={PLATFORMS} {...editForm.getInputProps('platform')} />
            <Select label="Status" data={STATUSES} {...editForm.getInputProps('status')} />
            <MultiSelect label="Projects" description="Which projects this bot can access (empty = all)" data={projectOptions} {...editForm.getInputProps('project_ids')} searchable clearable />
            <MultiSelect label="Workflows" description="Which workflows this bot can trigger (empty = all)" data={workflowOptions} {...editForm.getInputProps('workflow_ids')} searchable clearable />
            <MultiSelect label="Agent Roles" description="Which agent roles this bot can use (empty = all)" data={agentOptions} {...editForm.getInputProps('agent_ids')} searchable clearable />
            <Text size="xs" c="dimmed">Bot ID: {detailBot?.bot_id}</Text>
            <Group justify="space-between">
              <Button
                color="red"
                variant="outline"
                onClick={() => detailBot && handleDelete(detailBot.bot_id)}
                loading={deleteMutation.isPending}
              >
                Delete Bot
              </Button>
              <Button type="submit" loading={updateMutation.isPending}>Save Changes</Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </>
  );
}

// --- Connections Tab ---

function ConnectionsTab() {
  const [connections, setConnections] = useState<ChannelConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [addType, setAddType] = useState<string | null>(null);

  const fetchConnections = async () => {
    try {
      const data = await listChannelConnections();
      setConnections(data);
    } catch {
      // Silent fail — show empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchConnections();
  }, []);

  if (loading) return <Center py="xl"><Loader /></Center>;

  const slackConnections = connections.filter((c) => c.channel_type === 'slack');
  const telegramConnections = connections.filter((c) => c.channel_type === 'telegram');

  const hasSlack = slackConnections.length > 0;
  const hasTelegram = telegramConnections.length > 0;

  // Only show "Add" options for types not yet connected
  const addOptions = [
    ...(!hasSlack ? [{ value: 'slack', label: 'Slack' }] : []),
    ...(!hasTelegram ? [{ value: 'telegram', label: 'Telegram' }] : []),
  ];

  return (
    <Stack gap="md">
      {addOptions.length > 0 && (
        <Group justify="flex-end">
          <Select
            size="xs"
            placeholder="Add connection..."
            value={addType}
            onChange={(v) => {
              setAddType(v);
              if (v) {
                setConnections((prev) => [
                  ...prev,
                  { channel_type: v, connected: false, bot_username: '' } as ChannelConnection,
                ]);
                setAddType(null);
              }
            }}
            data={addOptions}
            clearable
            w={220}
          />
        </Group>
      )}
      {!hasSlack && slackConnections.length === 0 && telegramConnections.length === 0 && connections.length === 0 && (
        <EmptyState
          title="No connections configured"
          description="Connect a messaging platform like Slack or Telegram to get started"
        />
      )}
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        {slackConnections.map((c, i) => (
          <SlackConnectionCard
            key={`slack-${i}`}
            connection={c}
            onUpdate={() => void fetchConnections()}
            onRemove={() => {
              if (c.connected) void disconnectSlack().then(() => fetchConnections());
              else setConnections((prev) => prev.filter((p) => p !== c));
            }}
          />
        ))}
        {/* Show blank Slack card only if user explicitly added one */}
        {!hasSlack && connections.some((c) => c.channel_type === 'slack' && !c.connected) &&
          connections.filter((c) => c.channel_type === 'slack' && !c.connected).map((c, i) => (
            <SlackConnectionCard
              key={`slack-new-${i}`}
              connection={c}
              onUpdate={() => void fetchConnections()}
              onRemove={() => setConnections((prev) => prev.filter((p) => p !== c))}
            />
          ))
        }
        {telegramConnections.map((c, i) => (
          <TelegramConnectionCard
            key={`tg-${i}`}
            connection={c}
            onUpdate={() => void fetchConnections()}
            onRemove={() => {
              if (c.connected) void disconnectTelegram().then(() => fetchConnections());
              else setConnections((prev) => prev.filter((p) => p !== c));
            }}
          />
        ))}
        {/* Show blank Telegram card only if user explicitly added one */}
        {!hasTelegram && connections.some((c) => c.channel_type === 'telegram' && !c.connected) &&
          connections.filter((c) => c.channel_type === 'telegram' && !c.connected).map((c, i) => (
            <TelegramConnectionCard
              key={`tg-new-${i}`}
              connection={c}
              onUpdate={() => void fetchConnections()}
              onRemove={() => setConnections((prev) => prev.filter((p) => p !== c))}
            />
          ))
        }
      </SimpleGrid>
    </Stack>
  );
}

// --- Main Page ---

export function Component() {
  return (
    <Stack gap="md">
      <Title order={2}>Bots & Channels</Title>
      <Tabs defaultValue="bots">
        <Tabs.List>
          <Tabs.Tab value="bots" leftSection={<IconRobot size={16} />}>Bots</Tabs.Tab>
          <Tabs.Tab value="connections" leftSection={<IconPlug size={16} />}>Connections</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="bots" pt="md">
          <BotsTab />
        </Tabs.Panel>

        <Tabs.Panel value="connections" pt="md">
          <ConnectionsTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
