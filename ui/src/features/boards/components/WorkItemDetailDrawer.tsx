import { useState, useEffect } from 'react';
import {
  Drawer,
  TextInput,
  Textarea,
  Select,
  Stack,
  Group,
  Button,
  Text,
  Badge,
  TagsInput,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useUpdateWorkItem } from '../api';
import type { WorkItem } from '../api';
import { useQueryClient } from '@tanstack/react-query';

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

interface WorkItemDetailDrawerProps {
  item: WorkItem | null;
  opened: boolean;
  onClose: () => void;
}

export function WorkItemDetailDrawer({ item, opened, onClose }: WorkItemDetailDrawerProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [workType, setWorkType] = useState('task');
  const [status, setStatus] = useState('open');
  const [assignee, setAssignee] = useState('');
  const [tags, setTags] = useState<string[]>([]);

  const updateMut = useUpdateWorkItem();
  const qc = useQueryClient();

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
    <Drawer opened={opened} onClose={onClose} title="Work Item Details" position="right" size="md">
      <Stack gap="sm">
        <Group gap={4}>
          <Badge size="xs" variant="light" color="dimmed">
            {item.work_item_id.slice(0, 8)}
          </Badge>
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

        {item.branch_name && (
          <Text size="xs" c="dimmed">
            Branch: {item.branch_name}
          </Text>
        )}

        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={updateMut.isPending}>
            Save
          </Button>
        </Group>
      </Stack>
    </Drawer>
  );
}
