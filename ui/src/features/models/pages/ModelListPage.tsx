import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch, NumberInput, TagsInput,
  Textarea, Text, Tabs,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPlug } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useModelsListModels,
  useModelsCreateModel,
  useModelsUpdateModel,
  useModelsDeleteModel,
  useModelsCreateAssignment,
  useModelsDeleteAssignment,
  useModelsListModelAssignments,
} from '@/generated/api/models/models';
import type { ModelItem, ModelAssignmentItem } from '@/generated/api/models/models';
import { useAiProvidersListAiProviders } from '@/generated/api/ai-providers/ai-providers';
import { EmptyState } from '@/shared/components/EmptyState';

const CONTEXT_OPTIONS = [
  { value: 'task', label: 'Task' },
  { value: 'chat', label: 'Chat' },
  { value: 'workflow_step', label: 'Workflow Step' },
  { value: 'pipeline_step', label: 'Pipeline Step' },
  { value: 'agent_role', label: 'Agent Role' },
];

const contextColor: Record<string, string> = {
  task: 'blue', chat: 'green', workflow_step: 'orange', pipeline_step: 'violet', agent_role: 'red',
};

const providerTypeColor: Record<string, string> = {
  anthropic: 'violet', openai: 'green', azure_openai: 'blue', google: 'red', ollama: 'gray',
};

interface ProviderOption {
  value: string;
  label: string;
  type: string;
}

export function Component() {
  const { data: modelsResp, isLoading } = useModelsListModels();
  const { data: providersResp } = useAiProvidersListAiProviders();
  const createMut = useModelsCreateModel();
  const updateMut = useModelsUpdateModel();
  const deleteMut = useModelsDeleteModel();
  const createAssignMut = useModelsCreateAssignment();
  const deleteAssignMut = useModelsDeleteAssignment();
  const qc = useQueryClient();

  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<ModelItem | null>(null);
  const [assignModal, setAssignModal] = useState<string | null>(null);

  const providers: ProviderOption[] = ((providersResp?.data ?? []) as Array<{
    provider_id: string; name: string; provider_type: string;
  }>).map((p) => ({
    value: p.provider_id,
    label: `${p.name} (${p.provider_type})`,
    type: p.provider_type,
  }));

  const form = useForm({
    initialValues: {
      provider_id: '',
      name: '',
      model_name: '',
      max_tokens: 4096,
      temperature: 0.0,
      is_default: false,
      capabilities: [] as string[],
      config: '',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      model_name: (v) => (v.trim() ? null : 'Required'),
      provider_id: (v) => (v ? null : 'Select a provider'),
    },
  });

  const editForm = useForm({
    initialValues: {
      name: '',
      model_name: '',
      max_tokens: 4096,
      temperature: 0.0,
      is_default: false,
      capabilities: [] as string[],
      config: '',
    },
  });

  const assignForm = useForm({
    initialValues: { context: 'task', context_id: '', priority: 0 },
    validate: { context_id: (v) => (v.trim() ? null : 'Required') },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const models = (modelsResp?.data ?? []) as ModelItem[];

  const handleCreate = form.onSubmit((values) => {
    let config: Record<string, unknown> = {};
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch {
        notifications.show({ title: 'Error', message: 'Invalid JSON config', color: 'red' });
        return;
      }
    }
    createMut.mutate(
      { data: { ...values, config: Object.keys(config).length ? config : undefined } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Model added', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create model', color: 'red' }),
      },
    );
  });

  const openEdit = (m: ModelItem) => {
    setEditItem(m);
    editForm.setValues({
      name: m.name,
      model_name: m.model_name,
      max_tokens: m.max_tokens,
      temperature: m.temperature,
      is_default: m.is_default,
      capabilities: m.capabilities ?? [],
      config: m.config ? JSON.stringify(m.config, null, 2) : '',
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editItem) return;
    let config: Record<string, unknown> | undefined;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch {
        notifications.show({ title: 'Error', message: 'Invalid JSON', color: 'red' });
        return;
      }
    }
    updateMut.mutate(
      { modelId: editItem.model_id, data: { ...values, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Model updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          setEditItem(null);
        },
      },
    );
  });

  const handleDelete = (id: string) => {
    deleteMut.mutate({ modelId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Model removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
        if (editItem?.model_id === id) setEditItem(null);
      },
    });
  };

  const handleAssign = assignForm.onSubmit((values) => {
    if (!assignModal) return;
    createAssignMut.mutate(
      { modelId: assignModal, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Assigned', message: 'Model assignment created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          void qc.invalidateQueries({ queryKey: [`/api/v1/models/${assignModal}/assignments`] });
          assignForm.reset(); setAssignModal(null);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create assignment', color: 'red' }),
      },
    );
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Models</Title>
        <Button onClick={open}>Add Model</Button>
      </Group>

      {models.length === 0 ? (
        <EmptyState
          title="No models configured"
          description="Add AI models from your providers and assign them to tasks, chats, workflow steps, or agent roles"
          actionLabel="Add Model"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Model</Table.Th>
              <Table.Th>Provider</Table.Th>
              <Table.Th>Capabilities</Table.Th>
              <Table.Th>Default</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {models.map((m) => (
              <Table.Tr key={m.model_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(m)}>
                <Table.Td>{m.name}</Table.Td>
                <Table.Td><Text size="sm" c="dimmed" ff="monospace">{m.model_name}</Text></Table.Td>
                <Table.Td>
                  <Badge color={providerTypeColor[m.provider_type] ?? 'gray'} variant="light">
                    {m.provider_name || m.provider_type}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {(m.capabilities ?? []).slice(0, 3).map((c) => (
                      <Badge key={c} size="sm" variant="outline">{c}</Badge>
                    ))}
                    {(m.capabilities?.length ?? 0) > 3 && (
                      <Badge size="sm" variant="outline">+{m.capabilities.length - 3}</Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>{m.is_default && <Badge color="blue">Default</Badge>}</Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <ActionIcon variant="subtle" onClick={(e) => { e.stopPropagation(); setAssignModal(m.model_id); }}>
                      <IconPlug size={16} />
                    </ActionIcon>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(m.model_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create Modal */}
      <Modal opened={opened} onClose={close} title="Add Model" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select label="Provider" data={providers} searchable {...form.getInputProps('provider_id')} />
            <TextInput label="Display Name" placeholder="Claude Sonnet 4" {...form.getInputProps('name')} />
            <TextInput label="Model Name" placeholder="claude-sonnet-4-20250514" description="The litellm model identifier" {...form.getInputProps('model_name')} />
            <Group grow>
              <NumberInput label="Max Tokens" min={1} {...form.getInputProps('max_tokens')} />
              <NumberInput label="Temperature" min={0} max={2} step={0.1} decimalScale={1} {...form.getInputProps('temperature')} />
            </Group>
            <TagsInput label="Capabilities" placeholder="coding, planning, review..." {...form.getInputProps('capabilities')} />
            <Switch label="Set as default model" {...form.getInputProps('is_default', { type: 'checkbox' })} />
            <Textarea label="Extra Config (JSON)" minRows={2} styles={{ input: { fontFamily: 'monospace' } }} {...form.getInputProps('config')} />
            <Button type="submit" loading={createMut.isPending}>Add Model</Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        {editItem && (
          <Tabs defaultValue="details">
            <Tabs.List>
              <Tabs.Tab value="details">Details</Tabs.Tab>
              <Tabs.Tab value="assignments">Assignments</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="details" pt="sm">
              <form onSubmit={handleEdit}>
                <Stack gap="sm">
                  <TextInput label="Display Name" {...editForm.getInputProps('name')} />
                  <TextInput label="Model Name" {...editForm.getInputProps('model_name')} />
                  <Group grow>
                    <NumberInput label="Max Tokens" min={1} {...editForm.getInputProps('max_tokens')} />
                    <NumberInput label="Temperature" min={0} max={2} step={0.1} decimalScale={1} {...editForm.getInputProps('temperature')} />
                  </Group>
                  <TagsInput label="Capabilities" {...editForm.getInputProps('capabilities')} />
                  <Switch label="Default model" {...editForm.getInputProps('is_default', { type: 'checkbox' })} />
                  <Textarea label="Config (JSON)" minRows={2} styles={{ input: { fontFamily: 'monospace' } }} {...editForm.getInputProps('config')} />
                  <Button type="submit" loading={updateMut.isPending}>Save</Button>
                </Stack>
              </form>
            </Tabs.Panel>

            <Tabs.Panel value="assignments" pt="sm">
              <AssignmentsList modelId={editItem.model_id} onDelete={(id) => {
                deleteAssignMut.mutate({ assignmentId: id }, {
                  onSuccess: () => {
                    void qc.invalidateQueries({ queryKey: [`/api/v1/models/${editItem.model_id}/assignments`] });
                    notifications.show({ title: 'Removed', message: 'Assignment removed', color: 'orange' });
                  },
                });
              }} />
            </Tabs.Panel>
          </Tabs>
        )}
      </Modal>

      {/* Assign Modal */}
      <Modal opened={!!assignModal} onClose={() => { setAssignModal(null); assignForm.reset(); }} title="Assign Model">
        <form onSubmit={handleAssign}>
          <Stack gap="sm">
            <Select label="Context" data={CONTEXT_OPTIONS} {...assignForm.getInputProps('context')} />
            <TextInput
              label="Context ID"
              placeholder={assignForm.values.context === 'agent_role' ? 'planner, coder, reviewer...' : 'Step or task identifier'}
              description="The specific item this model is assigned to"
              {...assignForm.getInputProps('context_id')}
            />
            <NumberInput label="Priority" description="Higher = preferred" min={0} {...assignForm.getInputProps('priority')} />
            <Button type="submit" loading={createAssignMut.isPending}>Assign</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}

function AssignmentsList({ modelId, onDelete }: { modelId: string; onDelete: (id: string) => void }) {
  const { data: resp, isLoading } = useModelsListModelAssignments(modelId);
  if (isLoading) return <Center py="sm"><Loader size="sm" /></Center>;
  const assignments = (resp?.data ?? []) as ModelAssignmentItem[];
  if (assignments.length === 0) return <Text c="dimmed" size="sm" py="sm">No assignments yet</Text>;
  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Context</Table.Th>
          <Table.Th>ID</Table.Th>
          <Table.Th>Priority</Table.Th>
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {assignments.map((a) => (
          <Table.Tr key={a.assignment_id}>
            <Table.Td><Badge color={contextColor[a.context] ?? 'gray'} variant="light">{a.context}</Badge></Table.Td>
            <Table.Td><Text size="sm" ff="monospace">{a.context_id}</Text></Table.Td>
            <Table.Td>{a.priority}</Table.Td>
            <Table.Td>
              <ActionIcon color="red" variant="subtle" onClick={() => onDelete(a.assignment_id)}>
                <IconTrash size={14} />
              </ActionIcon>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
