import { Card, Group, Text, Badge, ActionIcon, Stack } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { MemoryTypeBadge } from './MemoryTypeBadge';
import type { MemoryFact } from '../hooks/useMemory';

interface MemoryCardProps {
  memory: MemoryFact;
  onDelete?: (id: string) => void;
  onClick?: (memory: MemoryFact) => void;
}

export function MemoryCard({ memory, onDelete, onClick }: MemoryCardProps) {
  const createdDate = new Date(memory.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <Card
      shadow="xs"
      padding="md"
      radius="md"
      withBorder
      style={{ cursor: onClick ? 'pointer' : undefined }}
      onClick={() => onClick?.(memory)}
    >
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs">
            <MemoryTypeBadge type={memory.memory_type} />
            <Badge variant="outline" size="sm" color="teal">
              {memory.fact_type}
            </Badge>
          </Group>
          {onDelete && (
            <ActionIcon
              variant="subtle"
              color="red"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(memory.id);
              }}
              aria-label="Delete memory"
            >
              <IconTrash size={14} />
            </ActionIcon>
          )}
        </Group>
        <Text size="sm" lineClamp={3}>
          {memory.content}
        </Text>
        <Group justify="space-between">
          <Text size="xs" c="dimmed">
            {createdDate}
          </Text>
          {memory.source_workflow_id && (
            <Text size="xs" c="dimmed">
              Workflow: {memory.source_workflow_id.slice(0, 8)}...
            </Text>
          )}
        </Group>
      </Stack>
    </Card>
  );
}
