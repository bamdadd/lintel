import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Switch,
  Loader, Center, ActionIcon, Badge, Textarea, Text, Paper, Code,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPlug, IconPlugOff, IconTool } from '@tabler/icons-react';
import { EmptyState } from '@/shared/components/EmptyState';

interface MCPServerItem {
  server_id: string;
  name: string;
  url: string;
  enabled: boolean;
  description: string;
  config: Record<string, unknown> | null;
}

interface MCPTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

const API = '/api/v1/mcp-servers';

export function Component() {
  const [servers, setServers] = useState<MCPServerItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<MCPServerItem | null>(null);
  const [toolsModal, setToolsModal] = useState<string | null>(null);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);

  const loadServers = () => {
    fetch(API).then(r => r.json()).then(d => { setServers(d); setIsLoading(false); })
      .catch(() => setIsLoading(false));
  };

  // Load on mount
  useState(() => { loadServers(); });

  const form = useForm({
    initialValues: { name: '', url: '', enabled: true, description: '', config: '' },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      url: (v) => (v.trim() ? null : 'URL is required'),
    },
  });

  const editForm = useForm({
    initialValues: { name: '', url: '', enabled: true, description: '', config: '' },
  });

  const handleCreate = form.onSubmit((values) => {
    let config: Record<string, unknown> = {};
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch {
        notifications.show({ title: 'Error', message: 'Invalid JSON config', color: 'red' }); return;
      }
    }
    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...values, config }),
    }).then(r => {
      if (!r.ok) throw new Error();
      notifications.show({ title: 'Created', message: 'MCP Server added', color: 'green' });
      form.reset(); close(); loadServers();
    }).catch(() => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }));
  });

  const openEdit = (s: MCPServerItem) => {
    setEditItem(s);
    editForm.setValues({
      name: s.name,
      url: s.url,
      enabled: s.enabled,
      description: s.description,
      config: s.config ? JSON.stringify(s.config, null, 2) : '',
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editItem) return;
    let config: Record<string, unknown> | undefined;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch {
        notifications.show({ title: 'Error', message: 'Invalid JSON', color: 'red' }); return;
      }
    }
    fetch(`${API}/${editItem.server_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...values, config }),
    }).then(r => {
      if (!r.ok) throw new Error();
      notifications.show({ title: 'Updated', message: 'Server updated', color: 'green' });
      setEditItem(null); loadServers();
    }).catch(() => notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' }));
  });

  const handleDelete = (id: string) => {
    fetch(`${API}/${id}`, { method: 'DELETE' }).then(() => {
      notifications.show({ title: 'Deleted', message: 'Server removed', color: 'orange' });
      if (editItem?.server_id === id) setEditItem(null);
      loadServers();
    });
  };

  const handleShowTools = (serverId: string) => {
    setToolsModal(serverId);
    setToolsLoading(true);
    setTools([]);
    fetch(`${API}/${serverId}/tools`)
      .then(r => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(d => { setTools(d); setToolsLoading(false); })
      .catch(() => {
        notifications.show({ title: 'Error', message: 'Failed to fetch tools', color: 'red' });
        setToolsLoading(false);
      });
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const toolsServer = servers.find(s => s.server_id === toolsModal);

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>MCP Servers</Title>
        <Button onClick={open}>Add Server</Button>
      </Group>

      <Text size="sm" c="dimmed">
        Connect external MCP servers to make their tools available in chat conversations.
      </Text>

      {servers.length === 0 ? (
        <EmptyState
          title="No MCP servers"
          description="Add MCP servers to give the chat AI access to external tools"
          actionLabel="Add Server"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>URL</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {servers.map((s) => (
              <Table.Tr key={s.server_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(s)}>
                <Table.Td>{s.name}</Table.Td>
                <Table.Td><Code>{s.url}</Code></Table.Td>
                <Table.Td>
                  <Badge
                    color={s.enabled ? 'green' : 'gray'}
                    variant="light"
                    leftSection={s.enabled ? <IconPlug size={12} /> : <IconPlugOff size={12} />}
                  >
                    {s.enabled ? 'Enabled' : 'Disabled'}
                  </Badge>
                </Table.Td>
                <Table.Td><Text size="sm" truncate maw={200}>{s.description}</Text></Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="blue"
                      onClick={(e) => { e.stopPropagation(); handleShowTools(s.server_id); }}
                      title="View tools"
                    >
                      <IconTool size={14} />
                    </ActionIcon>
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={(e) => { e.stopPropagation(); handleDelete(s.server_id); }}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create modal */}
      <Modal opened={opened} onClose={close} title="Add MCP Server" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My MCP Server" {...form.getInputProps('name')} />
            <TextInput label="URL" placeholder="http://localhost:8000/mcp" {...form.getInputProps('url')} />
            <Textarea label="Description" placeholder="What tools does this server provide?" {...form.getInputProps('description')} />
            <Switch label="Enabled" {...form.getInputProps('enabled', { type: 'checkbox' })} />
            <Textarea
              label="Extra Config (JSON)"
              minRows={2}
              styles={{ input: { fontFamily: 'monospace' } }}
              {...form.getInputProps('config')}
            />
            <Button type="submit">Add Server</Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit modal */}
      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <TextInput label="URL" {...editForm.getInputProps('url')} />
            <Textarea label="Description" {...editForm.getInputProps('description')} />
            <Switch label="Enabled" {...editForm.getInputProps('enabled', { type: 'checkbox' })} />
            <Textarea
              label="Config (JSON)"
              minRows={2}
              styles={{ input: { fontFamily: 'monospace' } }}
              {...editForm.getInputProps('config')}
            />
            <Button type="submit">Save</Button>
          </Stack>
        </form>
      </Modal>

      {/* Tools modal */}
      <Modal
        opened={!!toolsModal}
        onClose={() => { setToolsModal(null); setTools([]); }}
        title={`Tools: ${toolsServer?.name ?? ''}`}
        size="lg"
      >
        {toolsLoading ? (
          <Center py="xl"><Loader /></Center>
        ) : tools.length === 0 ? (
          <Text c="dimmed" ta="center" py="md">No tools found or server unreachable</Text>
        ) : (
          <Stack gap="sm">
            {tools.map((t) => (
              <Paper key={t.name} withBorder p="sm">
                <Group justify="space-between" mb={4}>
                  <Badge size="sm">{t.name}</Badge>
                </Group>
                <Text size="sm">{t.description}</Text>
              </Paper>
            ))}
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
