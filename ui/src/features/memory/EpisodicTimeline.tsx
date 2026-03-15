import { Timeline, Text, Badge, Group, Center, Loader, Stack } from '@mantine/core';
import { IconMessageCircle } from '@tabler/icons-react';
import { useMemoryList } from './hooks/useMemory';

interface EpisodicTimelineProps {
  projectId: string;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function groupByDate(items: Array<{ created_at: string; [key: string]: unknown }>): Map<string, typeof items> {
  const groups = new Map<string, typeof items>();
  for (const item of items) {
    const dateKey = new Date(item.created_at).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
    const group = groups.get(dateKey);
    if (group) {
      group.push(item);
    } else {
      groups.set(dateKey, [item]);
    }
  }
  return groups;
}

export function EpisodicTimeline({ projectId }: EpisodicTimelineProps) {
  const { data: resp, isLoading } = useMemoryList({
    project_id: projectId,
    memory_type: 'episodic',
    page: 1,
    page_size: 50,
  });

  const items = resp?.data?.items ?? [];

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (items.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No memories yet — memories are created automatically after workflow completions
      </Text>
    );
  }

  const grouped = groupByDate(items);

  return (
    <Stack gap="lg">
      {Array.from(grouped.entries()).map(([dateLabel, memories]) => (
        <Stack key={dateLabel} gap="xs">
          <Text fw={600} size="sm" c="dimmed">
            {dateLabel}
          </Text>
          <Timeline active={memories.length - 1} bulletSize={24} lineWidth={2}>
            {memories.map((memory) => (
              <Timeline.Item
                key={memory.id as string}
                bullet={<IconMessageCircle size={12} />}
                title={
                  <Group gap="xs">
                    <Badge variant="outline" size="xs" color="teal">
                      {memory.fact_type as string}
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {formatRelativeTime(memory.created_at)}
                    </Text>
                  </Group>
                }
              >
                <Text size="sm" c="dimmed" lineClamp={2} mt={4}>
                  {memory.content as string}
                </Text>
              </Timeline.Item>
            ))}
          </Timeline>
        </Stack>
      ))}
    </Stack>
  );
}
