import { useState } from 'react';
import {
  Modal,
  TextInput,
  Textarea,
  Select,
  Button,
  Stack,
  TagsInput,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

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
];

interface CreateWorkItemModalProps {
  opened: boolean;
  onClose: () => void;
  projectId: string;
}

export function CreateWorkItemModal({ opened, onClose, projectId }: CreateWorkItemModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [workType, setWorkType] = useState('task');
  const [status, setStatus] = useState('open');
  const [assignee, setAssignee] = useState('');
  const [tags, setTags] = useState<string[]>([]);

  const qc = useQueryClient();
  const createWorkItem = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      customInstance('/api/v1/work-items', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] }),
  });

  const handleSubmit = () => {
    if (!title.trim()) return;
    createWorkItem.mutate(
      {
        project_id: projectId,
        title: title.trim(),
        description,
        work_type: workType,
        status,
        assignee_agent_role: assignee,
        tags,
      },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Work item added', color: 'green' });
          setTitle('');
          setDescription('');
          setWorkType('task');
          setStatus('open');
          setAssignee('');
          setTags([]);
          onClose();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create work item', color: 'red' });
        },
      },
    );
  };

  return (
    <Modal opened={opened} onClose={onClose} title="New Work Item">
      <Stack gap="sm">
        <TextInput
          label="Title"
          placeholder="What needs to be done?"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
          required
        />
        <Textarea
          label="Description"
          placeholder="Details..."
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
          minRows={3}
          autosize
        />
        <Select label="Type" data={WORK_TYPES} value={workType} onChange={(v) => setWorkType(v ?? 'task')} />
        <Select label="Status" data={STATUSES} value={status} onChange={(v) => setStatus(v ?? 'open')} />
        <TextInput
          label="Assignee (agent role)"
          placeholder="e.g. coder, reviewer"
          value={assignee}
          onChange={(e) => setAssignee(e.currentTarget.value)}
        />
        <TagsInput label="Tags" value={tags} onChange={setTags} placeholder="Add tags" />
        <Button onClick={handleSubmit} loading={createWorkItem.isPending} disabled={!title.trim()} mt="sm">
          Create
        </Button>
      </Stack>
    </Modal>
  );
}
