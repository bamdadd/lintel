import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select, Textarea, MultiSelect,
  Loader, Center, ActionIcon, Badge, Text, Paper, SimpleGrid,
  ThemeIcon, Progress, Tooltip,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconPlayerStop, IconPlayerPlay, IconCircleCheck,
  IconCircleX, IconClock, IconSearch,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  usePipelinesListPipelines,
  usePipelinesCreatePipeline,
  usePipelinesDeletePipeline,
  usePipelinesCancelPipeline,
} from '@/generated/api/pipelines/pipelines';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';
import { EmptyState } from '@/shared/components/EmptyState';
import { regulationHooks } from '@/features/compliance/api';
import { TimeAgo } from '@/shared/components/TimeAgo';
import { StatusBadge } from '@/shared/components/StatusBadge';

interface PipelineRun {
  run_id: string;
  project_id: string;
  workflow_definition_id: string;
  status: string;
  trigger_type: string;
  trigger_id: string;
  work_item_id?: string;
  created_at: string;
  finished_at: string;
}

interface ProjectItem { project_id: string; name: string; }

function StatusSummaryCard({
  label, count, total, color, icon, active, onClick,
}: {
  label: string; count: number; total: number; color: string;
  icon: React.ReactNode; active: boolean; onClick: () => void;
}) {
  return (
    <Paper
      withBorder
      p="md"
      radius="md"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderColor: active ? `var(--mantine-color-${color}-5)` : undefined,
        transition: 'border-color 150ms, transform 150ms',
        transform: active ? 'scale(1.02)' : 'scale(1)',
      }}
    >
      <Group justify="space-between" mb="xs">
        <Text size="xs" c="dimmed" tt="uppercase" fw={600} style={{ letterSpacing: '0.05em' }}>
          {label}
        </Text>
        {icon}
      </Group>
      <Text size="xl" fw={700}>{count}</Text>
      {total > 0 && (
        <Progress
          value={(count / total) * 100}
          color={color}
          size={4}
          mt="xs"
          radius="xl"
        />
      )}
    </Paper>
  );
}

export function Component() {
  const { data: resp, isLoading } = usePipelinesListPipelines();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = usePipelinesCreatePipeline();
  const deleteMut = usePipelinesDeletePipeline();
  const cancelMut = usePipelinesCancelPipeline();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const { data: workflowsResp } = useWorkflowDefinitionsListWorkflowDefinitions();

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const workflowOptions = (Array.isArray(workflowsResp?.data) ? workflowsResp.data : [])
    .map((w: Record<string, unknown>) => ({
      value: String(w.definition_id ?? ''),
      label: String(w.name ?? w.definition_id ?? ''),
    }))
    .filter((o) => o.value !== '');

  const form = useForm({
    initialValues: { project_id: '', workflow_definition_id: '', trigger: 'manual', trigger_context: '', regulation_ids: [] as string[], industry_context: 'general' },
  });

  const isRegulationWorkflow = form.values.workflow_definition_id === 'regulation_to_policy';
  const { data: regulationsResp } = regulationHooks.useList(form.values.project_id || undefined);
  const regulations = (regulationsResp?.data ?? []) as unknown as { regulation_id: string; name: string }[];
  const regulationOptions = regulations.map((r) => ({ value: r.regulation_id, label: r.name }));

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const allRuns = [...((resp?.data ?? []) as PipelineRun[])].sort(
    (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
  );

  const counts = {
    running: allRuns.filter((r) => r.status === 'running').length,
    succeeded: allRuns.filter((r) => r.status === 'succeeded' || r.status === 'completed').length,
    failed: allRuns.filter((r) => r.status === 'failed' || r.status === 'error').length,
    pending: allRuns.filter((r) => r.status === 'pending' || r.status === 'waiting_approval').length,
  };

  const runs = allRuns.filter((r) => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      const pName = projects.find((p) => p.project_id === r.project_id)?.name ?? '';
      return (
        r.run_id.toLowerCase().includes(s)
        || pName.toLowerCase().includes(s)
        || r.trigger_type?.toLowerCase().includes(s)
      );
    }
    return true;
  });

  const handleCreate = form.onSubmit((values) => {
    const data: Record<string, unknown> = { ...values };
    if (values.workflow_definition_id === 'regulation_to_policy' && values.regulation_ids.length > 0) {
      data.trigger_context = JSON.stringify({
        regulation_ids: values.regulation_ids,
        industry_context: values.industry_context,
        additional_context: values.trigger_context,
      });
    }
    delete data.regulation_ids;
    delete data.industry_context;
    createMut.mutate(
      { data: data as any },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Pipeline started', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to start pipeline', color: 'red' }),
      },
    );
  });

  const handleCancel = (runId: string) => {
    cancelMut.mutate(
      { runId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Cancelled', message: 'Pipeline cancelled', color: 'orange' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
        },
      },
    );
  };

  const handleDelete = (runId: string) => {
    deleteMut.mutate(
      { runId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Pipeline removed', color: 'orange' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
        },
      },
    );
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? id;

  const toggleFilter = (status: string) => {
    setStatusFilter((prev) => (prev === status ? null : status));
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Pipelines</Title>
        <Button leftSection={<IconPlayerPlay size={16} />} onClick={open}>
          Run Pipeline
        </Button>
      </Group>

      {/* Status summary cards */}
      {allRuns.length > 0 && (
        <SimpleGrid cols={{ base: 2, sm: 4 }}>
          <StatusSummaryCard
            label="Running"
            count={counts.running}
            total={allRuns.length}
            color="blue"
            icon={<ThemeIcon variant="light" color="blue" size="sm" radius="xl"><IconPlayerPlay size={14} /></ThemeIcon>}
            active={statusFilter === 'running'}
            onClick={() => toggleFilter('running')}
          />
          <StatusSummaryCard
            label="Succeeded"
            count={counts.succeeded}
            total={allRuns.length}
            color="green"
            icon={<ThemeIcon variant="light" color="green" size="sm" radius="xl"><IconCircleCheck size={14} /></ThemeIcon>}
            active={statusFilter === 'succeeded'}
            onClick={() => toggleFilter('succeeded')}
          />
          <StatusSummaryCard
            label="Failed"
            count={counts.failed}
            total={allRuns.length}
            color="red"
            icon={<ThemeIcon variant="light" color="red" size="sm" radius="xl"><IconCircleX size={14} /></ThemeIcon>}
            active={statusFilter === 'failed'}
            onClick={() => toggleFilter('failed')}
          />
          <StatusSummaryCard
            label="Pending"
            count={counts.pending}
            total={allRuns.length}
            color="yellow"
            icon={<ThemeIcon variant="light" color="yellow" size="sm" radius="xl"><IconClock size={14} /></ThemeIcon>}
            active={statusFilter === 'pending'}
            onClick={() => toggleFilter('pending')}
          />
        </SimpleGrid>
      )}

      {allRuns.length === 0 ? (
        <EmptyState title="No pipeline runs" description="Start a pipeline to run workflows" actionLabel="Run Pipeline" onAction={open} />
      ) : (
        <>
          {/* Search bar */}
          <TextInput
            placeholder="Search by run ID, project, or trigger..."
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
          />

          <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Run</Table.Th>
                  <Table.Th>Project</Table.Th>
                  <Table.Th>Trigger</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Started</Table.Th>
                  <Table.Th w={80} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {runs.map((r) => (
                  <Table.Tr key={r.run_id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/pipelines/${r.run_id}`)}>
                    <Table.Td>
                      <Text size="sm" ff="monospace" fw={500}>{r.run_id?.slice(0, 8)}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" fw={500}>{projectName(r.project_id)}</Text>
                    </Table.Td>
                    <Table.Td>
                      {r.trigger_type?.startsWith('chat:') ? (
                        <Badge
                          variant="light"
                          style={{ cursor: 'pointer' }}
                          onClick={(e) => { e.stopPropagation(); navigate(`/chat/${r.trigger_type.split(':')[1]}`); }}
                        >
                          chat
                        </Badge>
                      ) : r.trigger_type?.startsWith('work_item:') ? (
                        <Badge
                          variant="light"
                          color="indigo"
                          style={{ cursor: 'pointer' }}
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              const resp = await fetch(`/api/v1/projects/${r.project_id}/boards`);
                              const boards = await resp.json();
                              const boardId = boards?.[0]?.board_id;
                              if (boardId) navigate(`/boards/${boardId}?work_item=${r.work_item_id}`);
                              else navigate('/boards');
                            } catch { navigate('/boards'); }
                          }}
                        >
                          work item
                        </Badge>
                      ) : (
                        <Badge variant="light" color="gray">{r.trigger_type || '—'}</Badge>
                      )}
                    </Table.Td>
                    <Table.Td><StatusBadge status={r.status} /></Table.Td>
                    <Table.Td><TimeAgo date={r.created_at} size="sm" /></Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        {r.status === 'running' && (
                          <Tooltip label="Cancel">
                            <ActionIcon color="orange" variant="subtle" size="sm" onClick={(e) => { e.stopPropagation(); handleCancel(r.run_id); }}>
                              <IconPlayerStop size={14} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                        <Tooltip label="Delete">
                          <ActionIcon color="red" variant="subtle" size="sm" onClick={(e) => { e.stopPropagation(); handleDelete(r.run_id); }}>
                            <IconTrash size={14} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
                {runs.length === 0 && (
                  <Table.Tr>
                    <Table.Td colSpan={6}>
                      <Text c="dimmed" ta="center" py="md">
                        No pipelines match your filters
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                )}
              </Table.Tbody>
            </Table>
          </Paper>
        </>
      )}

      <Modal opened={opened} onClose={close} title="Run Pipeline">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select label="Project" placeholder="Select project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <Select label="Workflow" placeholder="Select workflow" data={workflowOptions} searchable {...form.getInputProps('workflow_definition_id')} />
            {isRegulationWorkflow && (
              <>
                <MultiSelect label="Regulations" placeholder="Select regulations to convert" data={regulationOptions} searchable {...form.getInputProps('regulation_ids')} />
                <Select
                  label="Industry Context"
                  data={[
                    { value: 'general', label: 'General' },
                    { value: 'it', label: 'IT / Software' },
                    { value: 'health', label: 'Healthcare' },
                    { value: 'finance', label: 'Finance' },
                  ]}
                  {...form.getInputProps('industry_context')}
                />
              </>
            )}
            <Select label="Trigger" data={[{ value: 'manual', label: 'Manual' }, { value: 'webhook', label: 'Webhook' }, { value: 'schedule', label: 'Schedule' }]} {...form.getInputProps('trigger')} />
            <Textarea label="Additional Context" placeholder="Optional instructions or context for the workflow" autosize minRows={3} maxRows={8} {...form.getInputProps('trigger_context')} />
            <Button type="submit" loading={createMut.isPending}>Start Pipeline</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
