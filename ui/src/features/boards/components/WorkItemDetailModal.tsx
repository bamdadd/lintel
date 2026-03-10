import { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  Textarea,
  Select,
  Stack,
  Group,
  Button,
  Text,
  Badge,
  TagsInput,
  Divider,
  Anchor,
  Loader,
  Table,
  ThemeIcon,
} from '@mantine/core';
import { IconProgress, IconGitBranch, IconExternalLink } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useUpdateWorkItem, useDeleteWorkItem, usePipelinesForWorkItem } from '../api';
import type { WorkItem } from '../api';
import { useQueryClient } from '@tanstack/react-query';
import { StatusBadge } from '@/shared/components/StatusBadge';

const WORK_TYPES = [
  { value: 'task', label: 'Task' },
  { value: 'feature', label: 'Feature' },
  { value: 'bug', label: 'Bug' },
  { value: 'refactor', label: 'Refactor' },
];

const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'merged', label: 'Merged' },
  { value: 'closed', label: 'Closed' },
];


interface WorkItemDetailModalProps {
  item: WorkItem | null;
  opened: boolean;
  onClose: () => void;
}

export function WorkItemDetailModal({ item, opened, onClose }: WorkItemDetailModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [workType, setWorkType] = useState('task');
  const [status, setStatus] = useState('open');
  const [assignee, setAssignee] = useState('');
  const [tags, setTags] = useState<string[]>([]);

  const updateMut = useUpdateWorkItem();
  const deleteMut = useDeleteWorkItem();
  const qc = useQueryClient();
  const { data: pipelines, isLoading: pipelinesLoading } = usePipelinesForWorkItem(
    item?.work_item_id,
  );

  useEffect(() => {
    if (item) {
      setTitle(item.title);
      setDescription(item.description);
      setWorkType(item.work_type);
      setStatus(item.status);
      setAssignee(item.assignee_agent_role);
      setTags(item.tags ?? []);
    }
  }, [item]);

  const handleSave = () => {
    if (!item) return;
    const data: Record<string, unknown> = {};
    if (title !== item.title) data.title = title;
    if (description !== item.description) data.description = description;
    if (workType !== item.work_type) data.work_type = workType;
    if (status !== item.status) data.status = status;
    if (assignee !== item.assignee_agent_role) data.assignee_agent_role = assignee;
    if (JSON.stringify(tags) !== JSON.stringify(item.tags ?? [])) data.tags = tags;

    if (Object.keys(data).length === 0) {
      onClose();
      return;
    }

    updateMut.mutate(
      { workItemId: item.work_item_id, data },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
          void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
          notifications.show({ title: 'Saved', message: 'Work item updated', color: 'green' });
          onClose();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' });
        },
      },
    );
  };

  if (!item) return null;

  return (
    <Modal opened={opened} onClose={onClose} title="Work Item Details" size="lg">
      <Stack gap="sm">
        <Group gap={8}>
          <Badge size="xs" variant="light" color="dimmed">
            {item.work_item_id.slice(0, 8)}
          </Badge>
          <StatusBadge status={item.status} size="xs" />
        </Group>

        <TextInput label="Title" value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
        <Textarea
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
          minRows={3}
          autosize
        />
        <Group grow>
          <Select label="Type" data={WORK_TYPES} value={workType} onChange={(v) => setWorkType(v ?? 'task')} />
          <Select label="Status" data={STATUSES} value={status} onChange={(v) => setStatus(v ?? 'open')} />
        </Group>
        <TextInput
          label="Assignee (agent role)"
          value={assignee}
          onChange={(e) => setAssignee(e.currentTarget.value)}
          placeholder="e.g. coder, reviewer"
        />
        <TagsInput label="Tags" value={tags} onChange={setTags} placeholder="Add tags" />

        <Group justify="space-between">
          <Button
            color="red"
            variant="subtle"
            onClick={() => {
              if (!item || !window.confirm('Delete this work item?')) return;
              deleteMut.mutate(item.work_item_id, {
                onSuccess: () => {
                  void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
                  notifications.show({ title: 'Deleted', message: 'Work item removed', color: 'green' });
                  onClose();
                },
                onError: () => {
                  notifications.show({ title: 'Error', message: 'Failed to delete', color: 'red' });
                },
              });
            }}
            loading={deleteMut.isPending}
          >
            Delete
          </Button>
          <Group>
            <Button variant="default" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleSave} loading={updateMut.isPending}>
              Save
            </Button>
          </Group>
        </Group>

        <Divider label="Linked Resources" labelPosition="left" mt="sm" />

        {item.branch_name && (
          <Group gap="xs">
            <ThemeIcon size="sm" variant="light" color="gray">
              <IconGitBranch size={14} />
            </ThemeIcon>
            <Text size="sm">Branch: <Text span fw={500}>{item.branch_name}</Text></Text>
          </Group>
        )}

        {item.pr_url && (
          <Group gap="xs">
            <ThemeIcon size="sm" variant="light" color="blue">
              <IconExternalLink size={14} />
            </ThemeIcon>
            <Anchor href={item.pr_url} target="_blank" size="sm">
              Pull Request
            </Anchor>
          </Group>
        )}

        {item.thread_ref_str && (
          <Group gap="xs">
            <Text size="xs" c="dimmed">Thread: {item.thread_ref_str}</Text>
          </Group>
        )}

        <Text size="sm" fw={500} mt="xs">
          <Group gap={6}>
            <ThemeIcon size="sm" variant="light" color="violet">
              <IconProgress size={14} />
            </ThemeIcon>
            Pipelines
          </Group>
        </Text>

        {pipelinesLoading ? (
          <Loader size="sm" />
        ) : !pipelines || pipelines.length === 0 ? (
          <Text size="xs" c="dimmed">
            No pipelines linked. Moving to "In Progress" will trigger a workflow.
          </Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Run ID</Table.Th>
                <Table.Th>Workflow</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Created</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {pipelines.map((p) => (
                <Table.Tr key={p.run_id}>
                  <Table.Td>
                    <Anchor href={`/pipelines/${p.run_id}`} size="xs">
                      {p.run_id.slice(0, 8)}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">{p.workflow_definition_id}</Text>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={p.status} size="xs" />
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {p.created_at ? new Date(p.created_at).toLocaleString() : '—'}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Stack>
    </Modal>
  );
}
