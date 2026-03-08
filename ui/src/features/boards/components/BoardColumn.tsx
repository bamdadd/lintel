import { Paper, Text, ScrollArea, Stack } from '@mantine/core';
import { Droppable } from '@hello-pangea/dnd';
import type { WorkItem } from '../api';
import { WorkItemCard } from './WorkItemCard';

interface BoardColumnProps {
  columnId: string;
  name: string;
  items: WorkItem[];
  onClickItem?: (item: WorkItem) => void;
}

export function BoardColumn({ columnId, name, items, onClickItem }: BoardColumnProps) {
  return (
    <Paper
      withBorder
      p="sm"
      radius="md"
      style={{ width: 280, minWidth: 280, flexShrink: 0 }}
    >
      <Text fw={600} size="sm" mb="xs" c="dimmed" tt="uppercase">
        {name} ({items.length})
      </Text>
      <Droppable droppableId={columnId}>
        {(provided, snapshot) => (
          <ScrollArea
            h="calc(100vh - 220px)"
            ref={provided.innerRef}
            {...provided.droppableProps}
            style={{
              backgroundColor: snapshot.isDraggingOver
                ? 'var(--mantine-color-blue-light)'
                : undefined,
              borderRadius: 'var(--mantine-radius-sm)',
              minHeight: 60,
              transition: 'background-color 0.2s ease',
            }}
          >
            <Stack gap={0} p={4}>
              {items.map((item, idx) => (
                <WorkItemCard key={item.work_item_id} item={item} index={idx} onClickItem={onClickItem} />
              ))}
              {provided.placeholder}
            </Stack>
          </ScrollArea>
        )}
      </Droppable>
    </Paper>
  );
}
