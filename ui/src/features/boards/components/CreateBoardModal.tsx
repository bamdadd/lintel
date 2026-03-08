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
import { IconPlus, IconTrash, IconGripVertical } from '@tabler/icons-react';
import { DragDropContext, Droppable, Draggable, type DropResult } from '@hello-pangea/dnd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { useProjectsListProjects } from '@/generated/api/projects/projects';

interface ColumnDef {
  id: string;
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
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'merged', label: 'Merged' },
  { value: 'closed', label: 'Closed' },
  { value: 'failed', label: 'Failed' },
];

let nextId = 0;

function defaultColumns(): ColumnDef[] {
  return [
    { id: `c${++nextId}`, name: 'To Do', work_item_status: 'open' },
    { id: `c${++nextId}`, name: 'In Progress', work_item_status: 'in_progress' },
    { id: `c${++nextId}`, name: 'Done', work_item_status: 'closed' },
  ];
}

export function CreateBoardModal({ opened, onClose }: CreateBoardModalProps) {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];

  const [name, setName] = useState('');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnDef[]>(defaultColumns);

  const qc = useQueryClient();
  const createBoard = useMutation({
    mutationFn: (data: { project_id: string; name: string; columns: { name: string; position: number; work_item_status: string }[] }) =>
      customInstance('/api/v1/boards', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/boards'] }),
  });

  const addColumn = () => setColumns([...columns, { id: `c${++nextId}`, name: '', work_item_status: '' }]);
  const removeColumn = (i: number) => setColumns(columns.filter((_, idx) => idx !== i));
  const updateColumn = (i: number, field: 'name' | 'work_item_status', value: string) =>
    setColumns(columns.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)));

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;
    const next = [...columns];
    const moved = next.splice(result.source.index, 1)[0];
    if (!moved) return;
    next.splice(result.destination.index, 0, moved);
    setColumns(next);
  };

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
          setColumns(defaultColumns());
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
            Columns (drag to reorder)
          </Text>
          <ActionIcon variant="light" onClick={addColumn}>
            <IconPlus size={16} />
          </ActionIcon>
        </Group>

        <DragDropContext onDragEnd={handleDragEnd}>
          <Droppable droppableId="create-columns">
            {(provided) => (
              <Stack gap="xs" ref={provided.innerRef} {...provided.droppableProps}>
                {columns.map((col, i) => (
                  <Draggable key={col.id} draggableId={col.id} index={i}>
                    {(dragProvided, snapshot) => (
                      <Group
                        ref={dragProvided.innerRef}
                        {...dragProvided.draggableProps}
                        gap="xs"
                        align="center"
                        wrap="nowrap"
                        style={{
                          ...dragProvided.draggableProps.style,
                          opacity: snapshot.isDragging ? 0.8 : 1,
                        }}
                      >
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          style={{ cursor: 'grab' }}
                          {...dragProvided.dragHandleProps}
                        >
                          <IconGripVertical size={16} />
                        </ActionIcon>
                        <TextInput
                          placeholder="Column name"
                          value={col.name}
                          onChange={(e) => updateColumn(i, 'name', e.currentTarget.value)}
                          style={{ flex: 1 }}
                          required
                        />
                        <Select
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
                    )}
                  </Draggable>
                ))}
                {provided.placeholder}
              </Stack>
            )}
          </Droppable>
        </DragDropContext>

        <Button onClick={handleSubmit} loading={createBoard.isPending} disabled={!valid} mt="md">
          Create Board
        </Button>
      </Stack>
    </Modal>
  );
}
