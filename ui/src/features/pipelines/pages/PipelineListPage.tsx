import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconPlayerStop } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  usePipelinesListPipelines,
  usePipelinesCreatePipeline,
  usePipelinesDeletePipeline,
  usePipelinesCancelPipeline,
} from '@/generated/api/pipelines/pipelines';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';

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

const statusColor: Record<string, string> = {
  pending: 'gray', running: 'blue', succeeded: 'green', failed: 'red', cancelled: 'orange', waiting_approval: 'yellow',
};

export function Component() {
  const { data: resp, isLoading } = usePipelinesListPipelines();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = usePipelinesCreatePipeline();
  const deleteMut = usePipelinesDeletePipeline();
  const cancelMut = usePipelinesCancelPipeline();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const navigate = useNavigate();

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: { project_id: '', workflow_definition_id: '', trigger: 'manual' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const runs = [...((resp?.data ?? []) as PipelineRun[])].sort(
    (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime(),
  );

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
              <Table.Tr key={r.run_id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/pipelines/${r.run_id}`)}>
                <Table.Td><Text size="sm" ff="monospace">{r.run_id?.slice(0, 8)}</Text></Table.Td>
                <Table.Td>{projectName(r.project_id)}</Table.Td>
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
                    <Badge variant="light">{r.trigger_type || '—'}</Badge>
                  )}
                </Table.Td>
                <Table.Td><Badge color={statusColor[r.status] ?? 'gray'}>{r.status}</Badge></Table.Td>
                <Table.Td><TimeAgo date={r.created_at} size="sm" /></Table.Td>
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
