import { Paper, Text, Badge, Group } from '@mantine/core';
import { Draggable } from '@hello-pangea/dnd';
import type { WorkItem } from '../api';
import { useLatestPipelineWithStages } from '../api';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { PipelineStageIndicator } from './PipelineStageIndicator';

const typeColor: Record<string, string> = {
  feature: 'violet',
  bug: 'red',
  refactor: 'cyan',
  task: 'gray',
};

interface WorkItemCardProps {
  item: WorkItem;
  index: number;
  onClickItem?: (item: WorkItem) => void;
}

export function WorkItemCard({ item, index, onClickItem }: WorkItemCardProps) {
  const { pipeline, stages } = useLatestPipelineWithStages(item.work_item_id);

  return (
    <Draggable draggableId={item.work_item_id} index={index}>
      {(provided, snapshot) => (
        <Paper
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          p="sm"
          mb="xs"
          withBorder
          shadow={snapshot.isDragging ? 'md' : 'xs'}
          onClick={() => onClickItem?.(item)}
          style={{
            cursor: 'pointer',
            ...provided.draggableProps.style,
            opacity: snapshot.isDragging ? 0.9 : 1,
          }}
        >
          <Text size="sm" fw={500} mb={4} lineClamp={2}>
            {item.title}
          </Text>
          <Group gap={4} wrap="wrap">
            <Badge
              size="xs"
              color={typeColor[item.work_type] ?? 'gray'}
              variant="light"
            >
              {item.work_type}
            </Badge>
            <StatusBadge status={item.status} size="xs" />
          </Group>
          {item.tags?.length > 0 && (
            <Group gap={4} mt={4} wrap="wrap">
              {item.tags.map((tag) => (
                <Badge key={tag} size="xs" variant="outline" color="gray">
                  {tag}
                </Badge>
              ))}
            </Group>
          )}
          {pipeline && stages.length > 0 && (
            <PipelineStageIndicator pipeline={pipeline} stages={stages} />
          )}
        </Paper>
      )}
    </Draggable>
  );
}
