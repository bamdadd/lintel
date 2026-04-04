import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Select,
  Loader,
  Center,
  ActionIcon,
  Badge,
  Text,
  TagsInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { EmptyState } from '@/shared/components/EmptyState';

interface Bot {
  bot_id: string;
  name: string;
  platform: string;
  scopes: string[];
  status: string;
}

interface CreateBotPayload {
  name: string;
  platform: string;
  scopes: string[];
}

interface UpdateBotPayload {
  name?: string;
  platform?: string;
  scopes?: string[];
  status?: string;
}

type ListResponse = { data: Bot[]; status: number };
type ItemResponse = { data: Bot; status: number };

const QUERY_KEY = ['/api/v1/bots'];

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
    queryKey: QUERY_KEY,
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

export function Component() {
  const { data: resp, isLoading } = useBots();
  const createMutation = useCreateBot();
  const updateMutation = useUpdateBot();
  const deleteMutation = useDeleteBot();
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [detailBot, setDetailBot] = useState<Bot | null>(null);

  const createForm = useForm({
    initialValues: { name: '', platform: 'custom', scopes: [] as string[] },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: { name: '', platform: 'custom', scopes: [] as string[], status: 'active' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const bots = resp?.data ?? [];

  const handleCreate = createForm.onSubmit((values) => {
    createMutation.mutate(values, {
      onSuccess: () => {
        notifications.show({ title: 'Created', message: `Bot "${values.name}" created`, color: 'green' });
        void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
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
      name: bot.name,
      platform: bot.platform,
      scopes: bot.scopes ?? [],
      status: bot.status,
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!detailBot) return;
    updateMutation.mutate(
      { botId: detailBot.bot_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: `Bot "${values.name}" updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
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
        void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
        if (detailBot?.bot_id === botId) setDetailBot(null);
      },
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Bots</Title>
        <Button onClick={openCreate}>Add Bot</Button>
      </Group>

      {bots.length === 0 ? (
        <EmptyState
          title="No bots"
          description="Register bots to connect messaging platforms"
          actionLabel="Add Bot"
          onAction={openCreate}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Platform</Table.Th>
              <Table.Th>Scopes</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {bots.map((b) => (
              <Table.Tr key={b.bot_id} style={{ cursor: 'pointer' }} onClick={() => openDetail(b)}>
                <Table.Td>{b.name}</Table.Td>
                <Table.Td><Badge variant="light">{b.platform}</Badge></Table.Td>
                <Table.Td>
                  {b.scopes.length > 0
                    ? b.scopes.map((s) => <Badge key={s} variant="outline" size="sm" mr={4}>{s}</Badge>)
                    : <Text size="sm" c="dimmed">none</Text>}
                </Table.Td>
                <Table.Td><Badge color={statusColor(b.status)}>{b.status}</Badge></Table.Td>
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

      {/* Create Bot */}
      <Modal opened={createOpened} onClose={closeCreate} title="Add Bot">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My Slack Bot" {...createForm.getInputProps('name')} />
            <Select
              label="Platform"
              data={PLATFORMS}
              {...createForm.getInputProps('platform')}
            />
            <TagsInput
              label="Scopes"
              placeholder="Type scope and press Enter"
              {...createForm.getInputProps('scopes')}
            />
            <Button type="submit" loading={createMutation.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      {/* Bot Detail / Edit */}
      <Modal opened={!!detailBot} onClose={() => setDetailBot(null)} title={`Bot: ${detailBot?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Select
              label="Platform"
              data={PLATFORMS}
              {...editForm.getInputProps('platform')}
            />
            <Select
              label="Status"
              data={STATUSES}
              {...editForm.getInputProps('status')}
            />
            <TagsInput
              label="Scopes"
              placeholder="Type scope and press Enter"
              {...editForm.getInputProps('scopes')}
            />
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
    </Stack>
  );
}
