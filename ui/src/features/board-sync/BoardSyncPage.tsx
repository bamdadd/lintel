import { useState } from 'react';
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
  Badge,
  Text,
  Center,
  Loader,
  Card,
  ActionIcon,
  Tooltip,
  Paper,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconRefresh,
  IconTrash,
  IconArrowsExchange,
  IconPlus,
  IconBrandNotion,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EmptyState } from '@/shared/components/EmptyState';
import {
  listSyncConfigs,
  createSyncConfig,
  updateSyncConfig,
  deleteSyncConfig,
  triggerSync,
  connectNotion,
} from './boardSyncApi';
import type {
  SyncConfig,
  CreateSyncConfigPayload,
  UpdateSyncConfigPayload,
} from './boardSyncApi';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SYNC_CONFIGS_KEY = ['/api/v1/board-sync/configs'];

const PROVIDERS = [
  { value: 'notion', label: 'Notion' },
  { value: 'jira', label: 'Jira' },
];

const DIRECTIONS = [
  { value: 'pull', label: 'Pull (external \u2192 Lintel)' },
  { value: 'push', label: 'Push (Lintel \u2192 external)' },
  { value: 'bidirectional', label: 'Bidirectional' },
];

const CONFLICT_STRATEGIES = [
  { value: 'last_write_wins', label: 'Last write wins' },
  { value: 'manual', label: 'Manual resolution' },
];

function syncStatusColor(status: string): string {
  switch (status) {
    case 'connected': return 'green';
    case 'syncing': return 'blue';
    case 'error': return 'red';
    case 'disconnected':
    default: return 'gray';
  }
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

interface Board {
  board_id: string;
  name: string;
}

type ListBoardsResponse = { data: Board[]; status: number };

function useBoards() {
  return useQuery<ListBoardsResponse>({
    queryKey: ['/api/v1/boards'],
    queryFn: () => customInstance<ListBoardsResponse>('/api/v1/boards', { method: 'GET' }),
  });
}

// ---------------------------------------------------------------------------
// Sync Configs Tab
// ---------------------------------------------------------------------------

function SyncConfigsTab() {
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [editConfig, setEditConfig] = useState<SyncConfig | null>(null);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  const { data: boardsResp } = useBoards();
  const boards = boardsResp?.data ?? [];
  const boardOptions = boards.map((b) => ({ value: b.board_id, label: b.name || b.board_id }));

  const {
    data: configs,
    isLoading,
  } = useQuery({
    queryKey: SYNC_CONFIGS_KEY,
    queryFn: () => listSyncConfigs(),
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateSyncConfigPayload) => createSyncConfig(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SYNC_CONFIGS_KEY });
      notifications.show({ title: 'Created', message: 'Sync config created', color: 'green' });
      closeCreate();
      createForm.reset();
    },
    onError: () => {
      notifications.show({ title: 'Error', message: 'Failed to create sync config', color: 'red' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateSyncConfigPayload }) =>
      updateSyncConfig(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SYNC_CONFIGS_KEY });
      notifications.show({ title: 'Updated', message: 'Sync config updated', color: 'green' });
      setEditConfig(null);
    },
    onError: () => {
      notifications.show({ title: 'Error', message: 'Failed to update sync config', color: 'red' });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSyncConfig(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SYNC_CONFIGS_KEY });
      notifications.show({ title: 'Deleted', message: 'Sync config removed', color: 'orange' });
    },
  });

  const handleTriggerSync = async (configId: string) => {
    setSyncingIds((prev) => new Set(prev).add(configId));
    try {
      const result = await triggerSync(configId);
      notifications.show({
        title: 'Sync complete',
        message: `Pulled ${result.pulled}, pushed ${result.pushed}`,
        color: 'green',
      });
      void queryClient.invalidateQueries({ queryKey: SYNC_CONFIGS_KEY });
    } catch {
      notifications.show({ title: 'Sync failed', message: 'Could not trigger sync', color: 'red' });
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(configId);
        return next;
      });
    }
  };

  const createForm = useForm({
    initialValues: {
      board_id: '',
      provider: 'notion',
      direction: 'bidirectional',
      conflict_strategy: 'last_write_wins',
      external_database_id: '',
      external_project_key: '',
    },
    validate: {
      board_id: (v) => (v ? null : 'Board is required'),
      provider: (v) => (v ? null : 'Provider is required'),
    },
  });

  const editForm = useForm({
    initialValues: {
      direction: 'bidirectional',
      conflict_strategy: 'last_write_wins',
      external_database_id: '',
      external_project_key: '',
    },
  });

  const openEdit = (config: SyncConfig) => {
    setEditConfig(config);
    editForm.setValues({
      direction: config.direction,
      conflict_strategy: config.conflict_strategy,
      external_database_id: config.external_database_id,
      external_project_key: config.external_project_key,
    });
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const configList = configs ?? [];

  return (
    <>
      <Group justify="flex-end" mb="sm">
        <Button leftSection={<IconPlus size={16} />} onClick={openCreate}>
          Add Sync Config
        </Button>
      </Group>

      {configList.length === 0 ? (
        <EmptyState
          title="No sync configurations"
          description="Connect a board to an external provider like Notion or Jira to sync work items."
          actionLabel="Add Sync Config"
          onAction={openCreate}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Board</Table.Th>
              <Table.Th>Provider</Table.Th>
              <Table.Th>Direction</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Last Synced</Table.Th>
              <Table.Th>Items</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {configList.map((c) => {
              const board = boards.find((b) => b.board_id === c.board_id);
              return (
                <Table.Tr
                  key={c.sync_config_id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => openEdit(c)}
                >
                  <Table.Td>{board?.name ?? c.board_id}</Table.Td>
                  <Table.Td>
                    <Badge variant="light">{c.provider}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="outline" size="sm">{c.direction}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={syncStatusColor(c.status)}>{c.status}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {c.last_synced ? new Date(c.last_synced).toLocaleString() : 'Never'}
                    </Text>
                  </Table.Td>
                  <Table.Td>{c.items_in_sync}</Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      <Tooltip label="Trigger sync">
                        <ActionIcon
                          variant="subtle"
                          color="blue"
                          loading={syncingIds.has(c.sync_config_id)}
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleTriggerSync(c.sync_config_id);
                          }}
                        >
                          <IconRefresh size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Delete">
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteMutation.mutate(c.sync_config_id);
                          }}
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      {/* Create modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Add Sync Config" size="md">
        <form onSubmit={createForm.onSubmit((values) => createMutation.mutate(values))}>
          <Stack gap="sm">
            <Select
              label="Board"
              placeholder="Select a board"
              data={boardOptions}
              searchable
              {...createForm.getInputProps('board_id')}
            />
            <Select
              label="Provider"
              data={PROVIDERS}
              {...createForm.getInputProps('provider')}
            />
            <Select
              label="Sync Direction"
              data={DIRECTIONS}
              {...createForm.getInputProps('direction')}
            />
            <Select
              label="Conflict Strategy"
              data={CONFLICT_STRATEGIES}
              {...createForm.getInputProps('conflict_strategy')}
            />
            <TextInput
              label="External Database ID"
              description="Notion database ID or Jira project key"
              placeholder="abc123..."
              {...createForm.getInputProps('external_database_id')}
            />
            <TextInput
              label="External Project Key"
              description="Optional project key for Jira"
              {...createForm.getInputProps('external_project_key')}
            />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit modal */}
      <Modal
        opened={!!editConfig}
        onClose={() => setEditConfig(null)}
        title={`Edit Sync: ${editConfig?.provider ?? ''}`}
        size="md"
      >
        <form
          onSubmit={editForm.onSubmit((values) => {
            if (!editConfig) return;
            updateMutation.mutate({ id: editConfig.sync_config_id, payload: values });
          })}
        >
          <Stack gap="sm">
            <Select
              label="Sync Direction"
              data={DIRECTIONS}
              {...editForm.getInputProps('direction')}
            />
            <Select
              label="Conflict Strategy"
              data={CONFLICT_STRATEGIES}
              {...editForm.getInputProps('conflict_strategy')}
            />
            <TextInput
              label="External Database ID"
              {...editForm.getInputProps('external_database_id')}
            />
            <TextInput
              label="External Project Key"
              {...editForm.getInputProps('external_project_key')}
            />
            {editConfig && (
              <Paper p="xs" withBorder>
                <Group gap="xs">
                  <Text size="xs" c="dimmed">Status:</Text>
                  <StatusBadge status={editConfig.status} />
                  <Text size="xs" c="dimmed" ml="md">Last synced:</Text>
                  <Text size="xs">
                    {editConfig.last_synced
                      ? new Date(editConfig.last_synced).toLocaleString()
                      : 'Never'}
                  </Text>
                </Group>
              </Paper>
            )}
            <Text size="xs" c="dimmed">Config ID: {editConfig?.sync_config_id}</Text>
            <Group justify="space-between">
              <Button
                color="red"
                variant="outline"
                onClick={() => {
                  if (editConfig) {
                    deleteMutation.mutate(editConfig.sync_config_id);
                    setEditConfig(null);
                  }
                }}
              >
                Delete
              </Button>
              <Button type="submit" loading={updateMutation.isPending}>
                Save Changes
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------------------
// Notion Connection Tab
// ---------------------------------------------------------------------------

function NotionTab() {
  const [connectOpened, { open: openConnect, close: closeConnect }] = useDisclosure(false);

  const { data: projectsResp } = useQuery({
    queryKey: ['/api/v1/projects'],
    queryFn: () =>
      customInstance<{ data: Array<{ project_id: string; name: string }> }>(
        '/api/v1/projects',
        { method: 'GET' },
      ),
  });
  const projects = projectsResp?.data ?? [];
  const projectOptions = projects.map((p) => ({
    value: p.project_id,
    label: p.name || p.project_id,
  }));

  // There's no list endpoint for notion connections in the adapter, so we
  // just show the connect form. Future: add a list endpoint.

  const connectForm = useForm({
    initialValues: {
      project_id: '',
      database_id: '',
      api_key: '',
    },
    validate: {
      project_id: (v) => (v ? null : 'Project is required'),
      database_id: (v) => (v ? null : 'Database ID is required'),
      api_key: (v) => (v ? null : 'API key is required'),
    },
  });

  const connectMutation = useMutation({
    mutationFn: (payload: { project_id: string; database_id: string; api_key: string }) =>
      connectNotion(payload),
    onSuccess: () => {
      notifications.show({
        title: 'Connected',
        message: 'Notion database connected successfully',
        color: 'green',
      });
      connectForm.reset();
      closeConnect();
    },
    onError: () => {
      notifications.show({
        title: 'Error',
        message: 'Failed to connect Notion database',
        color: 'red',
      });
    },
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          Connect a Notion database to sync work items. You'll need a Notion integration API key
          and the target database ID.
        </Text>
        <Button
          leftSection={<IconBrandNotion size={16} />}
          onClick={openConnect}
        >
          Connect Notion
        </Button>
      </Group>

      <Card withBorder p="lg">
        <Stack gap="xs">
          <Group gap="xs">
            <IconBrandNotion size={20} />
            <Text fw={600}>Notion Integration</Text>
          </Group>
          <Text size="sm" c="dimmed">
            To connect Notion, create an internal integration at notion.so/my-integrations, then
            share your database with it. Use the integration token and database ID below.
          </Text>
        </Stack>
      </Card>

      <Modal opened={connectOpened} onClose={closeConnect} title="Connect Notion Database" size="md">
        <form onSubmit={connectForm.onSubmit((values) => connectMutation.mutate(values))}>
          <Stack gap="sm">
            <Select
              label="Project"
              placeholder="Select a project"
              data={projectOptions}
              searchable
              {...connectForm.getInputProps('project_id')}
            />
            <TextInput
              label="Notion Database ID"
              description="Found in the database URL after the workspace name"
              placeholder="a1b2c3d4..."
              {...connectForm.getInputProps('database_id')}
            />
            <TextInput
              label="API Key"
              description="Internal integration token from notion.so/my-integrations"
              placeholder="secret_..."
              type="password"
              {...connectForm.getInputProps('api_key')}
            />
            <Button type="submit" loading={connectMutation.isPending}>
              Connect
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function Component() {
  return (
    <Stack gap="md">
      <Title order={2}>Board Sync</Title>
      <Tabs defaultValue="configs">
        <Tabs.List>
          <Tabs.Tab value="configs" leftSection={<IconArrowsExchange size={16} />}>
            Sync Configs
          </Tabs.Tab>
          <Tabs.Tab value="notion" leftSection={<IconBrandNotion size={16} />}>
            Notion
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="configs" pt="md">
          <SyncConfigsTab />
        </Tabs.Panel>

        <Tabs.Panel value="notion" pt="md">
          <NotionTab />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
