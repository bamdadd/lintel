import { useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { Title, Stack, Group, Loader, Center, Text, ActionIcon, Button } from '@mantine/core';
import { IconSettings, IconPlus } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { DragDropContext, type DropResult } from '@hello-pangea/dnd';
import { useQueryClient } from '@tanstack/react-query';
import { useBoardsGetBoard, useWorkItemsForBoard, useUpdateWorkItem } from '../api';
import type { WorkItem } from '../api';
import { BoardColumn } from '../components/BoardColumn';
import { EditBoardModal } from '../components/EditBoardModal';
import { CreateWorkItemModal } from '../components/CreateWorkItemModal';
import { WorkItemDetailModal } from '../components/WorkItemDetailModal';
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
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [detailOpened, { open: openDetail, close: closeDetail }] = useDisclosure(false);
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false);
  const [createItemOpened, { open: openCreateItem, close: closeCreateItem }] = useDisclosure(false);

  const handleClickItem = (item: WorkItem) => {
    setSelectedItem(item);
    openDetail();
  };

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
    // Build a status-to-column lookup for fallback placement
    const statusToCol: Record<string, string> = {};
    for (const col of columns) {
      if (col.work_item_status) {
        statusToCol[col.work_item_status] = col.column_id;
      }
    }

    for (const item of items) {
      // Prefer status-based column when available (status is the source of truth),
      // fall back to explicit column_id for items without a status mapping
      let colId = statusToCol[item.status] ?? item.column_id ?? '';
      if (colId && map[colId]) {
        map[colId]!.push(item);
      } else {
        map['__unassigned__']!.push(item);
      }
    }
    // Sort by column_position within each column
    for (const key of Object.keys(map)) {
      map[key]!.sort((a, b) => (a.column_position ?? 0) - (b.column_position ?? 0));
    }
    return map;
  }, [itemsResp, columns]);

  const handleDragEnd = (result: DropResult) => {
    const { draggableId, source, destination } = result;
    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    const targetColumnId = destination.droppableId;
    const targetColumn = columns.find((c) => c.column_id === targetColumnId);
    const sourceColumnId = source.droppableId;

    // Build the new order for the target column
    const targetItems = [...(itemsByColumn[targetColumnId] ?? [])];
    const sourceItems = sourceColumnId === targetColumnId
      ? targetItems
      : [...(itemsByColumn[sourceColumnId] ?? [])];

    // Remove from source
    if (sourceColumnId === targetColumnId) {
      const moved = targetItems.splice(source.index, 1)[0];
      if (!moved) return;
      targetItems.splice(destination.index, 0, moved);
    } else {
      const moved = sourceItems.splice(source.index, 1)[0];
      if (!moved) return;
      targetItems.splice(destination.index, 0, moved);
    }

    // Update positions for all items in the target column
    const updates: Promise<unknown>[] = [];
    targetItems.forEach((item, i) => {
      const data: Record<string, unknown> = {
        column_id: targetColumnId === '__unassigned__' ? '' : targetColumnId,
        column_position: i,
      };
      if (item.work_item_id === draggableId && targetColumn?.work_item_status) {
        data.status = targetColumn.work_item_status;
      }
      if (item.column_position !== i || item.work_item_id === draggableId) {
        updates.push(
          updateMut.mutateAsync({ workItemId: item.work_item_id, data }),
        );
      }
    });

    // If cross-column, also update positions in the source column
    if (sourceColumnId !== targetColumnId) {
      sourceItems.forEach((item, i) => {
        if (item.column_position !== i) {
          updates.push(
            updateMut.mutateAsync({
              workItemId: item.work_item_id,
              data: { column_position: i },
            }),
          );
        }
      });
    }

    Promise.all(updates).then(
      () => void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] }),
      () => {
        notifications.show({
          title: 'Error',
          message: 'Failed to move work item',
          color: 'red',
        });
        void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
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
        <Group gap="xs">
          <Button leftSection={<IconPlus size={16} />} size="sm" onClick={openCreateItem}>
            New Work Item
          </Button>
          <ActionIcon variant="subtle" onClick={openEdit}>
            <IconSettings size={20} />
          </ActionIcon>
        </Group>
      </Group>
      <EditBoardModal board={board ?? null} opened={editOpened} onClose={closeEdit} />
      {board?.project_id && (
        <CreateWorkItemModal opened={createItemOpened} onClose={closeCreateItem} projectId={board.project_id} />
      )}

      <DragDropContext onDragEnd={handleDragEnd}>
        <Group gap="md" align="flex-start" wrap="nowrap" style={{ overflowX: 'auto' }}>
          {hasUnassigned && (
            <BoardColumn
              columnId="__unassigned__"
              name="Unassigned"
              items={itemsByColumn['__unassigned__'] ?? []}
              onClickItem={handleClickItem}
            />
          )}
          {columns.map((col) => (
            <BoardColumn
              key={col.column_id}
              columnId={col.column_id}
              name={col.name}
              items={itemsByColumn[col.column_id] ?? []}
              onClickItem={handleClickItem}
            />
          ))}
        </Group>
      </DragDropContext>

      <WorkItemDetailModal item={selectedItem} opened={detailOpened} onClose={closeDetail} />
    </Stack>
  );
}
