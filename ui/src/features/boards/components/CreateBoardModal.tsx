import { useState } from 'react';
import {
  Modal,
  TextInput,
  Select,
  Button,
  Stack,
  Group,
  ActionIcon,
  Text,
} from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { useProjectsListProjects } from '@/generated/api/projects/projects';

interface ColumnDef {
  name: string;
  work_item_status: string;
}

interface ProjectItem {
  project_id: string;
  name: string;
}

interface CreateBoardModalProps {
  opened: boolean;
  onClose: () => void;
}

const WORK_ITEM_STATUSES = [
  { value: '', label: '(none)' },
  { value: 'backlog', label: 'Backlog' },
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
];

export function CreateBoardModal({ opened, onClose }: CreateBoardModalProps) {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];

  const [name, setName] = useState('');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnDef[]>([
    { name: 'To Do', work_item_status: 'todo' },
    { name: 'In Progress', work_item_status: 'in_progress' },
    { name: 'Done', work_item_status: 'done' },
  ]);

  const qc = useQueryClient();
  const createBoard = useMutation({
    mutationFn: (data: { project_id: string; name: string; columns: { name: string; position: number; work_item_status: string }[] }) =>
      customInstance('/api/v1/boards', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/boards'] }),
  });

  const addColumn = () => setColumns([...columns, { name: '', work_item_status: '' }]);
  const removeColumn = (i: number) => setColumns(columns.filter((_, idx) => idx !== i));
  const updateColumn = (i: number, field: keyof ColumnDef, value: string) =>
    setColumns(columns.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)));

  const handleSubmit = () => {
    if (!projectId || !name.trim() || columns.length === 0) return;
    createBoard.mutate(
      {
        project_id: projectId,
        name: name.trim(),
        columns: columns.map((c, i) => ({
          name: c.name,
          position: i,
          work_item_status: c.work_item_status,
        })),
      },
      {
        onSuccess: () => {
          setName('');
          setProjectId(null);
          setColumns([
            { name: 'To Do', work_item_status: 'todo' },
            { name: 'In Progress', work_item_status: 'in_progress' },
            { name: 'Done', work_item_status: 'done' },
          ]);
          onClose();
        },
      },
    );
  };

  const valid = !!projectId && !!name.trim() && columns.length > 0 && columns.every((c) => c.name.trim());

  return (
    <Modal opened={opened} onClose={onClose} title="Create Board" size="lg">
      <Stack gap="sm">
        <TextInput
          label="Board Name"
          placeholder="My Board"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          required
        />
        <Select
          label="Project"
          placeholder="Select project"
          data={projects.map((p) => ({ value: p.project_id, label: p.name }))}
          value={projectId}
          onChange={setProjectId}
          required
        />

        <Group justify="space-between" mt="xs">
          <Text fw={500} size="sm">
            Columns
          </Text>
          <ActionIcon variant="light" onClick={addColumn}>
            <IconPlus size={16} />
          </ActionIcon>
        </Group>

        {columns.map((col, i) => (
          <Group key={i} gap="xs" align="flex-end">
            <TextInput
              label={i === 0 ? 'Name' : undefined}
              placeholder="Column name"
              value={col.name}
              onChange={(e) => updateColumn(i, 'name', e.currentTarget.value)}
              style={{ flex: 1 }}
              required
            />
            <Select
              label={i === 0 ? 'Status mapping' : undefined}
              placeholder="Status"
              data={WORK_ITEM_STATUSES}
              value={col.work_item_status}
              onChange={(v) => updateColumn(i, 'work_item_status', v ?? '')}
              w={150}
              clearable={false}
            />
            <ActionIcon color="red" variant="subtle" onClick={() => removeColumn(i)} disabled={columns.length <= 1}>
              <IconTrash size={16} />
            </ActionIcon>
          </Group>
        ))}

        <Button onClick={handleSubmit} loading={createBoard.isPending} disabled={!valid} mt="md">
          Create Board
        </Button>
      </Stack>
    </Modal>
  );
}
