import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPlayerStop } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  usePipelinesListPipelines,
  usePipelinesCreatePipeline,
  usePipelinesDeletePipeline,
  usePipelinesCancelPipeline,
  usePipelinesListStages,
} from '@/generated/api/pipelines/pipelines';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';

interface PipelineRun {
  run_id: string;
  project_id: string;
  workflow_definition_id: string;
  status: string;
  trigger: string;
  created_at: string;
  finished_at: string;
}

interface StageItem {
  stage_id: string;
  name: string;
  status: string;
  started_at: string;
  finished_at: string;
}

interface ProjectItem { project_id: string; name: string; }

const statusColor: Record<string, string> = {
  pending: 'gray', running: 'blue', succeeded: 'green', failed: 'red', cancelled: 'orange',
};

export function Component() {
  const { data: resp, isLoading } = usePipelinesListPipelines();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = usePipelinesCreatePipeline();
  const deleteMut = usePipelinesDeletePipeline();
  const cancelMut = usePipelinesCancelPipeline();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const { data: stagesResp } = usePipelinesListStages(selectedRun ?? '', {
    query: { enabled: !!selectedRun },
  });

  const projects = (projectsResp?.data ?? []) as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: { project_id: '', workflow_definition_id: '', trigger: 'manual' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const runs = (resp?.data ?? []) as PipelineRun[];
  const stages = (stagesResp?.data ?? []) as StageItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      { data: values },
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
          if (selectedRun === runId) setSelectedRun(null);
        },
      },
    );
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? id;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Pipelines</Title>
        <Button onClick={open}>Run Pipeline</Button>
      </Group>

      {runs.length === 0 ? (
        <EmptyState title="No pipeline runs" description="Start a pipeline to run workflows" actionLabel="Run Pipeline" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Run</Table.Th>
              <Table.Th>Project</Table.Th>
              <Table.Th>Trigger</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Started</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {runs.map((r) => (
              <Table.Tr key={r.run_id} style={{ cursor: 'pointer' }} onClick={() => setSelectedRun(r.run_id)}>
                <Table.Td><Text size="sm" ff="monospace">{r.run_id?.slice(0, 8)}</Text></Table.Td>
                <Table.Td>{projectName(r.project_id)}</Table.Td>
                <Table.Td><Badge variant="light">{r.trigger}</Badge></Table.Td>
                <Table.Td><Badge color={statusColor[r.status] ?? 'gray'}>{r.status}</Badge></Table.Td>
                <Table.Td><Text size="sm">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</Text></Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {r.status === 'running' && (
                      <ActionIcon color="orange" variant="subtle" onClick={(e) => { e.stopPropagation(); handleCancel(r.run_id); }}>
                        <IconPlayerStop size={16} />
                      </ActionIcon>
                    )}
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(r.run_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Stages panel */}
      <Modal opened={!!selectedRun} onClose={() => setSelectedRun(null)} title={`Stages: ${selectedRun?.slice(0, 8) ?? ''}`} size="lg">
        {stages.length === 0 ? (
          <Text c="dimmed">No stages for this run</Text>
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Stage</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Started</Table.Th>
                <Table.Th>Finished</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {stages.map((s) => (
                <Table.Tr key={s.stage_id}>
                  <Table.Td>{s.name}</Table.Td>
                  <Table.Td><Badge color={statusColor[s.status] ?? 'gray'}>{s.status}</Badge></Table.Td>
                  <Table.Td><Text size="sm">{s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</Text></Table.Td>
                  <Table.Td><Text size="sm">{s.finished_at ? new Date(s.finished_at).toLocaleString() : '—'}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Modal>

      <Modal opened={opened} onClose={close} title="Run Pipeline">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select label="Project" placeholder="Select project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <TextInput label="Workflow Definition ID" placeholder="workflow-id" {...form.getInputProps('workflow_definition_id')} />
            <Select label="Trigger" data={[{ value: 'manual', label: 'Manual' }, { value: 'webhook', label: 'Webhook' }, { value: 'schedule', label: 'Schedule' }]} {...form.getInputProps('trigger')} />
            <Button type="submit" loading={createMut.isPending}>Start Pipeline</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
