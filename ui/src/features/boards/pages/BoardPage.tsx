import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import {
  Title, Stack, Group, Loader, Center, Text, ActionIcon, Button,
  TextInput, MultiSelect, Switch, Tooltip,
} from '@mantine/core';
import { IconSettings, IconPlus, IconSearch, IconX, IconArrowsSort } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { DragDropContext, type DropResult } from '@hello-pangea/dnd';
import { useQueryClient } from '@tanstack/react-query';
import { useBoardsGetBoard, useWorkItemsForBoard, useUpdateWorkItem, useUpdateBoard } from '../api';
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
  const updateBoardMut = useUpdateBoard();
  const qc = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<WorkItem | null>(null);
  const [detailOpened, { open: openDetail, close: closeDetail }] = useDisclosure(false);
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false);
  const [createItemOpened, { open: openCreateItem, close: closeCreateItem }] = useDisclosure(false);

  const [searchParams, setSearchParams] = useSearchParams();

  // Track whether the user intentionally closed the modal to prevent re-open
  const [closedManually, setClosedManually] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterStatuses, setFilterStatuses] = useState<string[]>([]);

  const handleClickItem = (item: WorkItem) => {
    setSelectedItem(item);
    setClosedManually(false);
    setSearchParams({ work_item: item.work_item_id }, { replace: true });
    openDetail();
  };

  const handleCloseDetail = () => {
    setClosedManually(true);
    closeDetail();
    setSearchParams({}, { replace: true });
  };

  // Auto-open work item detail when linked via ?work_item=<id>
  const items = (itemsResp?.data ?? []) as WorkItem[];
  useEffect(() => {
    const workItemId = searchParams.get('work_item');
    if (workItemId && items.length > 0 && !detailOpened && !closedManually) {
      const found = items.find((i) => i.work_item_id === workItemId);
      if (found) {
        setSelectedItem(found);
        openDetail();
      }
    }
    // Reset closedManually when the param changes (e.g. new link clicked)
    if (!workItemId) {
      setClosedManually(false);
    }
  }, [searchParams, items, openDetail, detailOpened, closedManually]);

  // Derive unique tags and statuses for filter dropdowns
  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const item of items) {
      for (const tag of item.tags ?? []) set.add(tag);
    }
    return [...set].sort();
  }, [items]);

  const allStatuses = useMemo(() => {
    const set = new Set<string>();
    for (const item of items) {
      if (item.status) set.add(item.status);
    }
    return [...set].sort();
  }, [items]);

  const filteredItems = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return items.filter((item) => {
      if (q && !item.title.toLowerCase().includes(q)) return false;
      if (filterStatuses.length > 0 && !filterStatuses.includes(item.status)) return false;
      if (filterTags.length > 0 && !filterTags.some((t) => item.tags?.includes(t))) return false;
      return true;
    });
  }, [items, searchQuery, filterStatuses, filterTags]);

  const hasActiveFilters = searchQuery !== '' || filterTags.length > 0 || filterStatuses.length > 0;

  const columns = useMemo(
    () => [...(board?.columns ?? [])].sort((a, b) => a.position - b.position),
    [board],
  );

  const itemsByColumn = useMemo(() => {
    const items = filteredItems;
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
  }, [filteredItems, columns]);

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
      (err: unknown) => {
        const detail =
          err && typeof err === 'object' && 'body' in err
            ? (err as { body?: { detail?: string } }).body?.detail
            : undefined;
        notifications.show({
          title: detail?.includes('WIP limit') ? 'WIP Limit Reached' : 'Error',
          message: detail ?? 'Failed to move work item',
          color: detail?.includes('WIP limit') ? 'orange' : 'red',
          autoClose: detail?.includes('WIP limit') ? 8000 : 5000,
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
          <Tooltip label="When enabled, failed pipelines move items back to Todo and items auto-promote to In Progress when WIP has capacity">
            <IconArrowsSort size={16} style={{ opacity: 0.6 }} />
          </Tooltip>
          <Switch
            label="Auto Move"
            size="sm"
            checked={board.auto_move ?? false}
            onChange={(e) => {
              if (!boardId) return;
              const newVal = e.currentTarget.checked;
              // Optimistic update
              qc.setQueryData(
                ['/api/v1/boards', boardId],
                (old: typeof boardResp) =>
                  old ? { ...old, data: { ...old.data, auto_move: newVal } } : old,
              );
              updateBoardMut.mutate(
                { boardId, data: { auto_move: newVal } },
                {
                  onError: () =>
                    void qc.invalidateQueries({ queryKey: ['/api/v1/boards', boardId] }),
                },
              );
            }}
          />
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

      <Group gap="sm" wrap="wrap">
        <TextInput
          placeholder="Search by title..."
          leftSection={<IconSearch size={14} />}
          size="xs"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.currentTarget.value)}
          style={{ flex: '1 1 180px', maxWidth: 260 }}
          rightSection={searchQuery ? (
            <ActionIcon size="xs" variant="subtle" onClick={() => setSearchQuery('')}>
              <IconX size={12} />
            </ActionIcon>
          ) : undefined}
        />
        <MultiSelect
          placeholder="Filter by status"
          data={allStatuses}
          value={filterStatuses}
          onChange={setFilterStatuses}
          size="xs"
          clearable
          style={{ flex: '1 1 150px', maxWidth: 220 }}
        />
        <MultiSelect
          placeholder="Filter by tags"
          data={allTags}
          value={filterTags}
          onChange={setFilterTags}
          size="xs"
          clearable
          style={{ flex: '1 1 150px', maxWidth: 220 }}
        />
        {hasActiveFilters && (
          <Button
            variant="subtle"
            size="compact-xs"
            onClick={() => { setSearchQuery(''); setFilterTags([]); setFilterStatuses([]); }}
          >
            Clear filters
          </Button>
        )}
      </Group>

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
          {columns.map((col) => {
            const colItems = itemsByColumn[col.column_id] ?? [];
            if (col.name.toLowerCase() === 'backlog' && colItems.length === 0) return null;
            return (
              <BoardColumn
                key={col.column_id}
                columnId={col.column_id}
                name={col.name}
                items={colItems}
                wipLimit={col.wip_limit}
                onClickItem={handleClickItem}
              />
            );
          })}
        </Group>
      </DragDropContext>

      <WorkItemDetailModal item={selectedItem} opened={detailOpened} onClose={handleCloseDetail} />
    </Stack>
  );
}
