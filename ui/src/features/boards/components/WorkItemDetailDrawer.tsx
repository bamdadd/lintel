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
  TypographyStylesProvider,
  ActionIcon,
  Box,
} from '@mantine/core';
import { IconPencil } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@/features/chat/chat-markdown.css';
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

  const [editingDescription, setEditingDescription] = useState(false);
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
      setEditingDescription(false);
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

        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" fw={500}>Description</Text>
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={() => setEditingDescription((v) => !v)}
              title={editingDescription ? 'Preview' : 'Edit'}
            >
              <IconPencil size={14} />
            </ActionIcon>
          </Group>
          {editingDescription ? (
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
              minRows={6}
              autosize
              placeholder="Markdown supported..."
            />
          ) : description ? (
            <Box
              p="sm"
              style={{
                border: '1px solid var(--mantine-color-dark-4)',
                borderRadius: 'var(--mantine-radius-sm)',
                cursor: 'pointer',
              }}
              onClick={() => setEditingDescription(true)}
            >
              <TypographyStylesProvider>
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {description}
                  </ReactMarkdown>
                </div>
              </TypographyStylesProvider>
            </Box>
          ) : (
            <Text
              size="sm"
              c="dimmed"
              p="sm"
              style={{
                border: '1px dashed var(--mantine-color-dark-4)',
                borderRadius: 'var(--mantine-radius-sm)',
                cursor: 'pointer',
              }}
              onClick={() => setEditingDescription(true)}
            >
              Click to add a description...
            </Text>
          )}
        </Box>
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
