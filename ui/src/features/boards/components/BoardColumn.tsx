import { Badge, Paper, Progress, Text, Group, ScrollArea, Stack, Tooltip } from '@mantine/core';
import { Droppable } from '@hello-pangea/dnd';
import type { WorkItem } from '../api';
import { WorkItemCard } from './WorkItemCard';

interface BoardColumnProps {
  columnId: string;
  name: string;
  items: WorkItem[];
  wipLimit?: number;
  onClickItem?: (item: WorkItem) => void;
}

export function BoardColumn({ columnId, name, items, wipLimit, onClickItem }: BoardColumnProps) {
  const count = items.length;
  const isAtLimit = wipLimit != null && wipLimit > 0 && count >= wipLimit;
  const isOverLimit = wipLimit != null && wipLimit > 0 && count > wipLimit;
  const progressPct = wipLimit && wipLimit > 0 ? Math.min((count / wipLimit) * 100, 100) : 0;
  const progressColor = isOverLimit ? 'red' : isAtLimit ? 'orange' : 'blue';

  return (
    <Paper
      withBorder
      p="sm"
      radius="md"
      style={{
        width: 280,
        minWidth: 280,
        flexShrink: 0,
        borderColor: isOverLimit
          ? 'var(--mantine-color-red-4)'
          : isAtLimit
            ? 'var(--mantine-color-orange-4)'
            : undefined,
        borderWidth: isAtLimit || isOverLimit ? 2 : undefined,
      }}
    >
      <Group justify="space-between" mb={4}>
        <Text fw={600} size="sm" c="dimmed" tt="uppercase">
          {name}
        </Text>
        <Group gap={4}>
          <Badge
            size="sm"
            variant="light"
            color={isOverLimit ? 'red' : isAtLimit ? 'orange' : 'gray'}
          >
            {count}
            {wipLimit != null && wipLimit > 0 ? ` / ${wipLimit}` : ''}
          </Badge>
        </Group>
      </Group>

      {wipLimit != null && wipLimit > 0 && (
        <Tooltip label={`${count} of ${wipLimit} WIP slots used`}>
          <Progress
            value={progressPct}
            color={progressColor}
            size={4}
            mb="xs"
            radius="xl"
            animated={isAtLimit}
          />
        </Tooltip>
      )}

      <Droppable droppableId={columnId}>
        {(provided, snapshot) => (
          <ScrollArea
            h="calc(100vh - 240px)"
            ref={provided.innerRef}
            {...provided.droppableProps}
            style={{
              backgroundColor: snapshot.isDraggingOver
                ? isAtLimit
                  ? 'var(--mantine-color-red-light)'
                  : 'var(--mantine-color-blue-light)'
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
