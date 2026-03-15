import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch, NumberInput, TagsInput,
  Textarea, Text, Tabs, Alert, Divider, Paper, ThemeIcon, Tooltip, Box,
  SimpleGrid,
} from '@mantine/core';
import { Link } from 'react-router';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconAlertCircle, IconPencil, IconCheck, IconPlus,
  IconCpu, IconBrain,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useModelsListModels,
  useModelsCreateModel,
  useModelsUpdateModel,
  useModelsDeleteModel,
  useModelsCreateModelAssignment,
  useModelsDeleteModelAssignment,
  useModelsListModelAssignments,
} from '@/generated/api/models/models';
import {
  useAiProvidersListAiProviders,
  useAiProvidersListAvailableModels,
} from '@/generated/api/ai-providers/ai-providers';
import {
  useWorkflowDefinitionsListWorkflowDefinitions,
} from '@/generated/api/workflow-definitions/workflow-definitions';
import type { AiProvidersListAvailableModels200Item } from '@/generated/models';
import type { ModelAssignmentContext } from '@/generated/models/modelAssignmentContext';
import { EmptyState } from '@/shared/components/EmptyState';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ModelItem = Record<string, any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ModelAssignmentItem = Record<string, any>;
type AvailableModel = AiProvidersListAvailableModels200Item & {
  model_name: string; display_name: string; family: string;
  parameter_size: string; quantization_level: string; max_tokens: number; temperature: number;
};

const CONTEXT_OPTIONS = [
  { value: 'task', label: 'Task' },
  { value: 'chat', label: 'Chat' },
  { value: 'workflow_step', label: 'Workflow Step' },
  { value: 'pipeline_step', label: 'Pipeline Step' },
  { value: 'agent_role', label: 'Agent Role' },
];

const AGENT_ROLES = [
  { value: 'planner', label: 'Planner' },
  { value: 'coder', label: 'Coder' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'pm', label: 'PM' },
  { value: 'designer', label: 'Designer' },
  { value: 'summarizer', label: 'Summarizer' },
  { value: 'architect', label: 'Architect' },
  { value: 'qa_engineer', label: 'QA Engineer' },
  { value: 'devops', label: 'DevOps' },
  { value: 'security', label: 'Security' },
  { value: 'researcher', label: 'Researcher' },
  { value: 'tech_lead', label: 'Tech Lead' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'triage', label: 'Triage' },
];

const contextColor: Record<string, string> = {
  task: 'blue', chat: 'green', workflow_step: 'orange', pipeline_step: 'violet', agent_role: 'red',
};

const providerTypeColor: Record<string, string> = {
  anthropic: 'violet', openai: 'green', azure_openai: 'blue', google: 'red', ollama: 'gray', bedrock: 'orange',
};

const providerTypeIcon: Record<string, string> = {
  anthropic: 'A', openai: 'O', azure_openai: 'Az', google: 'G', ollama: 'Ol', bedrock: 'B',
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
  const createAssignMut = useModelsCreateModelAssignment();
  const deleteAssignMut = useModelsDeleteModelAssignment();
  const qc = useQueryClient();

  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<ModelItem | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const { data: editAssignmentsResp } = useModelsListModelAssignments(
    editItem?.model_id ?? '',
    { query: { enabled: !!editItem } },
  );
  const assignedIds = new Set(
    ((editAssignmentsResp?.data ?? []) as ModelAssignmentItem[]).map(
      (a) => `${a.context}:${a.context_id}`,
    ),
  );

  const { data: workflowDefsResp } = useWorkflowDefinitionsListWorkflowDefinitions();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const workflowDefs = (workflowDefsResp?.data ?? []) as Array<Record<string, any>>;

  const workflowStepOptions = (() => {
    const groups: { group: string; items: { value: string; label: string }[] }[] = [];
    const seen = new Set<string>();
    for (const wd of workflowDefs) {
      const name = wd.name as string;
      const stageNames = (wd.stage_names ?? []) as string[];
      const meta = (wd.graph?.node_metadata ?? {}) as Record<string, Record<string, string>>;
      const items: { value: string; label: string }[] = [];
      for (const s of stageNames) {
        if (seen.has(s)) continue;
        seen.add(s);
        items.push({ value: s, label: meta[s]?.label ?? s });
      }
      if (items.length > 0) groups.push({ group: name, items });
    }
    return groups;
  })();

  const providersList = (providersResp?.data ?? []) as Array<{
    provider_id: string; name: string; provider_type: string;
  }>;
  const providers: ProviderOption[] = providersList.map((p) => ({
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

  const selectedProvider = providersList.find((p) => p.provider_id === form.values.provider_id);
  const isOllamaProvider = selectedProvider?.provider_type === 'ollama';
  const isBedrockProvider = selectedProvider?.provider_type === 'bedrock';
  const hasModelDiscovery = isOllamaProvider || isBedrockProvider;

  const { data: availableModelsResp, isLoading: loadingAvailable } = useAiProvidersListAvailableModels(
    form.values.provider_id,
    { query: { enabled: hasModelDiscovery && !!form.values.provider_id } },
  );
  const availableModels = (availableModelsResp as { data?: AvailableModel[] } | undefined)?.data ?? [];
  const availableModelOptions = availableModels.map((m) => ({
    value: m.model_name,
    label: `${m.display_name} (${m.parameter_size || m.model_name})`,
  }));

  const handleAvailableModelSelect = (modelName: string | null) => {
    if (!modelName) return;
    form.setFieldValue('model_name', modelName);
    const selected = availableModels.find((m) => m.model_name === modelName);
    if (selected) {
      form.setFieldValue('name', selected.display_name);
      form.setFieldValue('max_tokens', selected.max_tokens);
      form.setFieldValue('temperature', selected.temperature);
    }
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const models = (modelsResp?.data ?? []) as ModelItem[];
  const hasProviders = providers.length > 0;

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
    assignForm.reset();
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

  const startRename = (m: ModelItem) => {
    setRenamingId(m.model_id);
    setRenameValue(m.name);
  };

  const submitRename = (modelId: string) => {
    if (!renameValue.trim()) return;
    updateMut.mutate(
      { modelId, data: { name: renameValue.trim() } },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          setRenamingId(null);
        },
      },
    );
  };

  const handleAssign = assignForm.onSubmit((values) => {
    if (!editItem) return;
    const modelId = editItem.model_id;
    createAssignMut.mutate(
      { modelId, data: { ...values, context: values.context as ModelAssignmentContext } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Assigned', message: 'Model assignment created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          void qc.invalidateQueries({ queryKey: [`/api/v1/models/${modelId}/assignments`] });
          assignForm.reset();
        },
        onError: () => notifications.show({
          title: 'Error', message: 'Failed to create assignment', color: 'red',
        }),
      },
    );
  });

  const handleAssignAllRoles = () => {
    if (!editItem) return;
    const modelId = editItem.model_id;
    const promises = AGENT_ROLES.map((role) =>
      createAssignMut.mutateAsync({
        modelId,
        data: {
          context: 'agent_role',
          context_id: role.value,
          priority: assignForm.values.priority,
        },
      }),
    );
    Promise.all(promises).then(() => {
      notifications.show({
        title: 'Assigned',
        message: `Model assigned to all ${AGENT_ROLES.length} agent roles`,
        color: 'green',
      });
      void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
      void qc.invalidateQueries({ queryKey: [`/api/v1/models/${modelId}/assignments`] });
      assignForm.reset();
    }).catch(() => {
      notifications.show({ title: 'Error', message: 'Failed to assign to some roles', color: 'red' });
    });
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Group gap="xs">
          <Title order={2}>Models</Title>
          {models.length > 0 && <Badge variant="light" size="lg">{models.length}</Badge>}
        </Group>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => {
            if (models.length === 0) form.setFieldValue('is_default', true);
            open();
          }}
          disabled={!hasProviders}
        >
          Add Model
        </Button>
      </Group>

      {!hasProviders && (
        <Alert icon={<IconAlertCircle size={16} />} title="No AI providers configured" color="yellow">
          You need to{' '}
          <Link to="../ai-providers" style={{ color: 'inherit', textDecoration: 'underline' }}>
            add an AI provider
          </Link>{' '}
          before you can add models.
        </Alert>
      )}

      {models.length === 0 && hasProviders ? (
        <EmptyState
          title="No models configured"
          description="Add AI models from your providers and assign them to tasks, chats, workflow steps, or agent roles"
          actionLabel="Add Model"
          onAction={() => { form.setFieldValue('is_default', true); open(); }}
        />
      ) : models.length === 0 ? null : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {models.map((m) => (
            <Paper
              key={m.model_id}
              withBorder
              p="lg"
              radius="md"
              style={{
                cursor: 'pointer',
                transition: 'transform 150ms ease, box-shadow 150ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
              }}
              onClick={() => openEdit(m)}
            >
              <Group justify="space-between" mb="sm" wrap="nowrap">
                <Group gap="sm" wrap="nowrap" style={{ overflow: 'hidden' }}>
                  <ThemeIcon
                    variant="light"
                    color={providerTypeColor[m.provider_type] ?? 'gray'}
                    size="md"
                    radius="md"
                  >
                    <Text size="xs" fw={700}>
                      {providerTypeIcon[m.provider_type] ?? '?'}
                    </Text>
                  </ThemeIcon>
                  <Box style={{ overflow: 'hidden' }}>
                    {renamingId === m.model_id ? (
                      <Group gap={4} onClick={(e) => e.stopPropagation()}>
                        <TextInput
                          size="xs"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.currentTarget.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') submitRename(m.model_id);
                            if (e.key === 'Escape') setRenamingId(null);
                          }}
                          autoFocus
                          style={{ flex: 1 }}
                        />
                        <ActionIcon size="xs" variant="filled" color="green" onClick={() => submitRename(m.model_id)}>
                          <IconCheck size={12} />
                        </ActionIcon>
                      </Group>
                    ) : (
                      <Group gap={4} wrap="nowrap" onClick={(e) => e.stopPropagation()}>
                        <Text size="sm" fw={600} truncate>{m.name}</Text>
                        <ActionIcon size="xs" variant="subtle" onClick={() => startRename(m)}>
                          <IconPencil size={12} />
                        </ActionIcon>
                      </Group>
                    )}
                    <Text size="xs" c="dimmed" ff="monospace" truncate>{m.model_name}</Text>
                  </Box>
                </Group>
                <Group gap={4} wrap="nowrap">
                  {m.is_default && (
                    <Badge color="blue" size="xs">Default</Badge>
                  )}
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleDelete(m.model_id); }}
                  >
                    <IconTrash size={14} />
                  </ActionIcon>
                </Group>
              </Group>

              <Group gap={4} mb="xs">
                <Badge color={providerTypeColor[m.provider_type] ?? 'gray'} variant="light" size="xs">
                  {m.provider_name || m.provider_type}
                </Badge>
              </Group>

              {(m.capabilities ?? []).length > 0 && (
                <Group gap={4}>
                  {(m.capabilities ?? []).slice(0, 3).map((c: string) => (
                    <Badge key={c} size="xs" variant="outline" color="gray">{c}</Badge>
                  ))}
                  {(m.capabilities?.length ?? 0) > 3 && (
                    <Badge size="xs" variant="outline" color="gray">+{m.capabilities.length - 3}</Badge>
                  )}
                </Group>
              )}
            </Paper>
          ))}
        </SimpleGrid>
      )}

      {/* Create Modal */}
      <Modal opened={opened} onClose={() => { close(); form.reset(); }} title="Add Model" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select
              label="Provider"
              data={providers}
              searchable
              {...form.getInputProps('provider_id')}
              onChange={(val) => {
                form.setFieldValue('provider_id', val ?? '');
                form.setFieldValue('model_name', '');
                form.setFieldValue('name', '');
                form.setFieldValue('max_tokens', 4096);
                form.setFieldValue('temperature', 0.0);
                if (models.length === 0) {
                  form.setFieldValue('is_default', true);
                }
              }}
            />
            {hasModelDiscovery ? (
              <Select
                label="Model"
                placeholder={
                  loadingAvailable
                    ? `Loading models from ${isBedrockProvider ? 'Bedrock' : 'Ollama'}...`
                    : 'Select a model'
                }
                data={availableModelOptions}
                searchable
                nothingFoundMessage={
                  loadingAvailable
                    ? 'Loading...'
                    : isBedrockProvider
                      ? 'No models found — check your AWS credentials and region'
                      : 'No models found — pull models in Ollama first'
                }
                value={form.values.model_name}
                onChange={handleAvailableModelSelect}
                error={form.errors.model_name}
                disabled={loadingAvailable}
                description={
                  availableModels.find((m) => m.model_name === form.values.model_name)
                    ? `${availableModels.find((m) => m.model_name === form.values.model_name)!.family}${availableModels.find((m) => m.model_name === form.values.model_name)!.parameter_size ? ` · ${availableModels.find((m) => m.model_name === form.values.model_name)!.parameter_size}` : ''}${availableModels.find((m) => m.model_name === form.values.model_name)!.quantization_level ? ` · ${availableModels.find((m) => m.model_name === form.values.model_name)!.quantization_level}` : ''}`
                    : undefined
                }
              />
            ) : (
              <TextInput
                label="Model Name"
                placeholder="claude-sonnet-4-20250514"
                description="The litellm model identifier"
                {...form.getInputProps('model_name')}
              />
            )}
            <TextInput
              label="Display Name"
              placeholder="e.g. Qwen (think off), Fast Claude..."
              description="A friendly name to identify this model in the UI"
              {...form.getInputProps('name')}
            />
            <Group grow>
              <NumberInput label="Max Tokens" min={1} {...form.getInputProps('max_tokens')} />
              <NumberInput
                label="Temperature"
                min={0} max={2} step={0.1} decimalScale={1}
                {...form.getInputProps('temperature')}
              />
            </Group>
            <TagsInput label="Capabilities" placeholder="coding, planning, review..." {...form.getInputProps('capabilities')} />
            <Switch label="Set as default model" {...form.getInputProps('is_default', { type: 'checkbox' })} />
            <Textarea label="Extra Config (JSON)" minRows={2} styles={{ input: { fontFamily: 'monospace' } }} {...form.getInputProps('config')} />
            <Button type="submit" loading={createMut.isPending}>Add Model</Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        opened={!!editItem}
        onClose={() => { setEditItem(null); assignForm.reset(); }}
        title={`Edit: ${editItem?.name ?? ''}`}
        size="lg"
      >
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
                    <NumberInput
                      label="Temperature"
                      min={0} max={2} step={0.1} decimalScale={1}
                      {...editForm.getInputProps('temperature')}
                    />
                  </Group>
                  <TagsInput label="Capabilities" {...editForm.getInputProps('capabilities')} />
                  <Switch label="Default model" {...editForm.getInputProps('is_default', { type: 'checkbox' })} />
                  <Textarea
                    label="Config (JSON)"
                    minRows={2}
                    styles={{ input: { fontFamily: 'monospace' } }}
                    {...editForm.getInputProps('config')}
                  />
                  <Button type="submit" loading={updateMut.isPending}>Save</Button>
                </Stack>
              </form>
            </Tabs.Panel>

            <Tabs.Panel value="assignments" pt="sm">
              <Stack gap="md">
                <AssignmentsList modelId={editItem.model_id} onDelete={(id) => {
                  deleteAssignMut.mutate({ assignmentId: id }, {
                    onSuccess: () => {
                      void qc.invalidateQueries({
                        queryKey: [`/api/v1/models/${editItem.model_id}/assignments`],
                      });
                      notifications.show({ title: 'Removed', message: 'Assignment removed', color: 'orange' });
                    },
                  });
                }} />

                <Divider label="Add assignment" labelPosition="center" />

                <form onSubmit={handleAssign}>
                  <Stack gap="sm">
                    <Select
                      label="Context"
                      data={CONTEXT_OPTIONS}
                      {...assignForm.getInputProps('context')}
                      onChange={(val) => {
                        assignForm.setFieldValue('context', val ?? 'task');
                        assignForm.setFieldValue('context_id', '');
                      }}
                    />
                    {assignForm.values.context === 'agent_role' ? (
                      <Select
                        label="Agent Role"
                        data={AGENT_ROLES.filter(
                          (r) => !assignedIds.has(`agent_role:${r.value}`),
                        )}
                        searchable
                        placeholder="Select an agent role"
                        {...assignForm.getInputProps('context_id')}
                      />
                    ) : assignForm.values.context === 'workflow_step'
                        || assignForm.values.context === 'pipeline_step' ? (
                      <Select
                        label="Step"
                        data={workflowStepOptions.map((g) => ({
                          ...g,
                          items: g.items.filter(
                            (i) => !assignedIds.has(`${assignForm.values.context}:${i.value}`),
                          ),
                        })).filter((g) => g.items.length > 0)}
                        searchable
                        placeholder="Select a workflow step"
                        {...assignForm.getInputProps('context_id')}
                      />
                    ) : (
                      <TextInput
                        label="Context ID"
                        placeholder="Step or task identifier"
                        description="The specific item this model is assigned to"
                        {...assignForm.getInputProps('context_id')}
                      />
                    )}
                    <NumberInput
                      label="Priority"
                      description="Higher = preferred"
                      min={0}
                      {...assignForm.getInputProps('priority')}
                    />
                    <Group>
                      <Button type="submit" loading={createAssignMut.isPending}>Assign</Button>
                      {assignForm.values.context === 'agent_role' && (
                        <Button
                          variant="light"
                          loading={createAssignMut.isPending}
                          onClick={handleAssignAllRoles}
                        >
                          Assign to All Roles
                        </Button>
                      )}
                    </Group>
                  </Stack>
                </form>
              </Stack>
            </Tabs.Panel>
          </Tabs>
        )}
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
            <Table.Td>
              <Badge color={contextColor[a.context] ?? 'gray'} variant="light">{a.context}</Badge>
            </Table.Td>
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
