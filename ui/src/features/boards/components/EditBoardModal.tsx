import { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  NumberInput,
  Select,
  Button,
  Stack,
  Group,
  ActionIcon,
  Text,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlus, IconTrash, IconGripVertical } from '@tabler/icons-react';
import { DragDropContext, Droppable, Draggable, type DropResult } from '@hello-pangea/dnd';
import { useQueryClient } from '@tanstack/react-query';
import { useUpdateBoard } from '../api';
import type { Board } from '../api';

interface ColumnDef {
  id: string;
  name: string;
  work_item_status: string;
  wip_limit: number;
}

interface EditBoardModalProps {
  board: Board | null;
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

let nextTempId = 0;
function tempId() {
  return `__new_${++nextTempId}`;
}

export function EditBoardModal({ board, opened, onClose }: EditBoardModalProps) {
  const [name, setName] = useState('');
  const [columns, setColumns] = useState<ColumnDef[]>([]);

  const qc = useQueryClient();
  const updateBoard = useUpdateBoard();

  useEffect(() => {
    if (board) {
      setName(board.name);
      setColumns(
        [...board.columns]
          .sort((a, b) => a.position - b.position)
          .map((c) => ({
            id: c.column_id,
            name: c.name,
            work_item_status: c.work_item_status,
            wip_limit: c.wip_limit ?? 0,
          })),
      );
    }
  }, [board]);

  const addColumn = () =>
    setColumns([...columns, { id: tempId(), name: '', work_item_status: '', wip_limit: 0 }]);
  const removeColumn = (i: number) => setColumns(columns.filter((_, idx) => idx !== i));
  const updateColumn = (i: number, field: keyof ColumnDef, value: string | number) =>
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
    if (!board || !name.trim() || columns.length === 0) return;
    updateBoard.mutate(
      {
        boardId: board.board_id,
        data: {
          name: name.trim(),
          columns: columns.map((c, i) => ({
            column_id: c.id.startsWith('__new_') ? undefined : c.id,
            name: c.name,
            position: i,
            work_item_status: c.work_item_status,
            wip_limit: c.wip_limit,
          })),
        },
      },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/boards'] });
          notifications.show({ title: 'Saved', message: 'Board updated', color: 'green' });
          onClose();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update board', color: 'red' });
        },
      },
    );
  };

  const valid = !!name.trim() && columns.length > 0 && columns.every((c) => c.name.trim());

  return (
    <Modal opened={opened} onClose={onClose} title="Edit Board" size="lg">
      <Stack gap="sm">
        <TextInput
          label="Board Name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
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
          <Droppable droppableId="edit-columns">
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
                          w={140}
                          clearable={false}
                        />
                        <Tooltip label="WIP limit (0 = unlimited)">
                          <NumberInput
                            placeholder="WIP"
                            value={col.wip_limit}
                            onChange={(v) => updateColumn(i, 'wip_limit', typeof v === 'number' ? v : 0)}
                            min={0}
                            max={100}
                            w={70}
                            size="sm"
                          />
                        </Tooltip>
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

        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={updateBoard.isPending} disabled={!valid}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
