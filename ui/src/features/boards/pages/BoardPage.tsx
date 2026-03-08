import { useMemo } from 'react';
import { useParams } from 'react-router';
import { Title, Stack, Group, Loader, Center, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { DragDropContext, type DropResult } from '@hello-pangea/dnd';
import { useQueryClient } from '@tanstack/react-query';
import { useBoardsGetBoard, useWorkItemsForBoard, useUpdateWorkItem } from '../api';
import type { WorkItem } from '../api';
import { BoardColumn } from '../components/BoardColumn';
import { EmptyState } from '@/shared/components/EmptyState';

export function Component() {
  const { boardId } = useParams<{ boardId: string }>();
  const { data: boardResp, isLoading: boardLoading } = useBoardsGetBoard(boardId);
  const board = boardResp?.data;

  const { data: itemsResp, isLoading: itemsLoading } = useWorkItemsForBoard(
    board?.project_id,
  );
  const updateMut = useUpdateWorkItem();
  const qc = useQueryClient();

  const columns = useMemo(
    () => [...(board?.columns ?? [])].sort((a, b) => a.position - b.position),
    [board],
  );

  const itemsByColumn = useMemo(() => {
    const items = (itemsResp?.data ?? []) as WorkItem[];
    const map: Record<string, WorkItem[]> = {};
    for (const col of columns) {
      map[col.column_id] = [];
    }
    // "Unassigned" for items not in any column
    map['__unassigned__'] = [];
    for (const item of items) {
      const colId = item.column_id || '__unassigned__';
      if (map[colId]) {
        map[colId].push(item);
      } else {
        map['__unassigned__'].push(item);
      }
    }
    // Sort by column_position within each column
    for (const key of Object.keys(map)) {
      map[key]!.sort((a, b) => (a.column_position ?? 0) - (b.column_position ?? 0));
    }
    return map;
  }, [itemsResp, columns]);

  const handleDragEnd = (result: DropResult) => {
    const { draggableId, destination } = result;
    if (!destination) return;

    const targetColumnId = destination.droppableId;
    const targetColumn = columns.find((c) => c.column_id === targetColumnId);

    const updateData: Record<string, unknown> = {
      column_id: targetColumnId === '__unassigned__' ? '' : targetColumnId,
      column_position: destination.index,
    };

    // If the column maps to a status, also update the work item status
    if (targetColumn?.work_item_status) {
      updateData.status = targetColumn.work_item_status;
    }

    updateMut.mutate(
      { workItemId: draggableId, data: updateData },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
        },
        onError: () => {
          notifications.show({
            title: 'Error',
            message: 'Failed to move work item',
            color: 'red',
          });
        },
      },
    );
  };

  if (boardLoading || itemsLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (!board) {
    return (
      <EmptyState
        title="Board not found"
        description="The board you're looking for doesn't exist."
      />
    );
  }

  if (columns.length === 0) {
    return (
      <Stack gap="md">
        <Title order={2}>{board.name}</Title>
        <EmptyState
          title="No columns"
          description="This board has no columns configured. Add columns to the board to get started."
        />
      </Stack>
    );
  }

  const hasUnassigned = (itemsByColumn['__unassigned__']?.length ?? 0) > 0;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <Title order={2}>{board.name}</Title>
          <Text size="sm" c="dimmed">
            Kanban
          </Text>
        </Group>
      </Group>

      <DragDropContext onDragEnd={handleDragEnd}>
        <Group gap="md" align="flex-start" wrap="nowrap" style={{ overflowX: 'auto' }}>
          {hasUnassigned && (
            <BoardColumn
              columnId="__unassigned__"
              name="Unassigned"
              items={itemsByColumn['__unassigned__'] ?? []}
            />
          )}
          {columns.map((col) => (
            <BoardColumn
              key={col.column_id}
              columnId={col.column_id}
              name={col.name}
              items={itemsByColumn[col.column_id] ?? []}
            />
          ))}
        </Group>
      </DragDropContext>
    </Stack>
  );
}
