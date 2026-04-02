import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Select, NumberInput, TextInput,
  Loader, Center, ActionIcon, Badge, Text, Paper, Tabs,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPlus, IconList, IconGrid3x3 } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router';
import {
  useModelsListModels,
  useModelsListAllAssignments,
  useModelsCreateModelAssignment,
  useModelsDeleteModelAssignment,
} from '@/generated/api/models/models';
import { useAgentsListAgentRoles } from '@/generated/api/agents/agents';
import type { ModelAssignmentContext } from '@/generated/models/modelAssignmentContext';
import { EmptyState } from '@/shared/components/EmptyState';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ModelItem = Record<string, any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AssignmentItem = Record<string, any>;

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

export function Component() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: modelsResp, isLoading: loadingModels } = useModelsListModels();
  const { data: allAssignResp, isLoading: loadingAssign } = useModelsListAllAssignments();
  const { data: rolesResp } = useAgentsListAgentRoles();
  const createMut = useModelsCreateModelAssignment();
  const deleteMut = useModelsDeleteModelAssignment();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const models = (modelsResp?.data ?? []) as ModelItem[];
  const allAssignments = (allAssignResp?.data ?? []) as AssignmentItem[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const agentRoles = (rolesResp?.data ?? rolesResp ?? []) as Array<Record<string, any>>;

  const modelOptions = models.map((m) => ({
    value: m.model_id as string,
    label: `${m.name} (${m.model_name})` as string,
  }));

  const roleOptions = agentRoles.length > 0
    ? agentRoles.map((r) => ({
        value: (r.value ?? r.name ?? r) as string,
        label: (r.label ?? r.display_name ?? r.name ?? r) as string,
      }))
    : [
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

  const contextIdOptions = (ctx: string) => {
    if (ctx === 'agent_role') return roleOptions;
    return [];
  };

  const form = useForm({
    initialValues: { model_id: '', context: 'agent_role', context_id: '', priority: 0 },
    validate: {
      model_id: (v) => (v ? null : 'Select a model'),
      context_id: (v) => (v.trim() ? null : 'Required'),
    },
  });

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      {
        modelId: values.model_id,
        data: {
          context: values.context as ModelAssignmentContext,
          context_id: values.context_id,
          priority: values.priority,
        },
      },
      {
        onSuccess: () => {
          notifications.show({ title: 'Assigned', message: 'Model assignment created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
          form.reset();
          setShowForm(false);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create assignment', color: 'red' }),
      },
    );
  });

  const handleDelete = (assignmentId: string) => {
    deleteMut.mutate({ assignmentId }, {
      onSuccess: () => {
        notifications.show({ title: 'Removed', message: 'Assignment removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/models'] });
      },
    });
  };

  const modelNameMap = Object.fromEntries(
    models.map((m) => [m.model_id, m.name]),
  ) as Record<string, string>;

  const isLoading = loadingModels || loadingAssign;
  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const activeTab = location.pathname.endsWith('/assignments') ? 'assignments' : 'models';

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Models</Title>
      </Group>

      <Tabs
        value={activeTab}
        onChange={(val) => {
          if (val === 'models') void navigate('../models');
          else if (val === 'assignments') void navigate('../models/assignments');
        }}
      >
        <Tabs.List>
          <Tabs.Tab value="models" leftSection={<IconGrid3x3 size={16} />}>Models</Tabs.Tab>
          <Tabs.Tab value="assignments" leftSection={<IconList size={16} />}>
            Assignments
            {allAssignments.length > 0 && (
              <Badge variant="light" size="sm" ml={6}>{allAssignments.length}</Badge>
            )}
          </Tabs.Tab>
        </Tabs.List>
      </Tabs>

      {models.length === 0 ? (
        <EmptyState
          title="No models configured"
          description="Add models first before creating assignments"
          actionLabel="Go to Models"
          onAction={() => void navigate('../models')}
        />
      ) : (
        <Stack gap="md">
          <Group justify="flex-end">
            <Button
              leftSection={<IconPlus size={16} />}
              onClick={() => setShowForm(!showForm)}
              variant={showForm ? 'light' : 'filled'}
            >
              {showForm ? 'Cancel' : 'New Assignment'}
            </Button>
          </Group>

          {showForm && (
            <Paper withBorder p="md" radius="md">
              <form onSubmit={handleCreate}>
                <Stack gap="sm">
                  <Group grow>
                    <Select
                      label="Model"
                      placeholder="Select model"
                      data={modelOptions}
                      searchable
                      {...form.getInputProps('model_id')}
                    />
                    <Select
                      label="Context"
                      data={CONTEXT_OPTIONS}
                      {...form.getInputProps('context')}
                      onChange={(val) => {
                        form.setFieldValue('context', val ?? 'agent_role');
                        form.setFieldValue('context_id', '');
                      }}
                    />
                  </Group>
                  <Group grow>
                    {contextIdOptions(form.values.context).length > 0 ? (
                      <Select
                        label="Context ID"
                        placeholder={`Select ${form.values.context.replace('_', ' ')}`}
                        data={contextIdOptions(form.values.context)}
                        searchable
                        {...form.getInputProps('context_id')}
                      />
                    ) : (
                      <TextInput
                        label="Context ID"
                        placeholder="Step or task identifier"
                        {...form.getInputProps('context_id')}
                      />
                    )}
                    <NumberInput
                      label="Priority"
                      description="Higher = preferred"
                      min={0}
                      {...form.getInputProps('priority')}
                    />
                  </Group>
                  <Group>
                    <Button type="submit" loading={createMut.isPending}>Create Assignment</Button>
                  </Group>
                </Stack>
              </form>
            </Paper>
          )}

          {allAssignments.length === 0 ? (
            <EmptyState
              title="No assignments yet"
              description="Assign models to agent roles, tasks, or workflow steps"
              actionLabel="New Assignment"
              onAction={() => setShowForm(true)}
            />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Model</Table.Th>
                  <Table.Th>Context</Table.Th>
                  <Table.Th>Context ID</Table.Th>
                  <Table.Th>Priority</Table.Th>
                  <Table.Th w={60} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {allAssignments.map((a) => (
                  <Table.Tr key={a.assignment_id}>
                    <Table.Td>
                      <Text size="sm" fw={500}>
                        {modelNameMap[a.model_id] ?? a.model_id}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={contextColor[a.context] ?? 'gray'} variant="light">
                        {a.context}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" ff="monospace">{a.context_id}</Text>
                    </Table.Td>
                    <Table.Td>{a.priority}</Table.Td>
                    <Table.Td>
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => handleDelete(a.assignment_id as string)}
                        loading={deleteMut.isPending}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>
      )}
    </Stack>
  );
}
