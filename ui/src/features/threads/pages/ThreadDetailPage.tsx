import { Title, Text, Stack, Loader, Center, Timeline } from '@mantine/core';
import { useParams } from 'react-router';
import { useEventsGetEventsByStream } from '@/generated/api/events/events';

export function Component() {
  const { streamId } = useParams<{ streamId: string }>();
  const { data: resp, isLoading } = useEventsGetEventsByStream(streamId ?? '');

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const responseData = resp?.data as { events?: Array<Record<string, unknown>> } | undefined;
  const events = responseData?.events ?? [];

  return (
    <Stack gap="md">
      <Title order={2}>Thread: {streamId}</Title>
      {events.length === 0 ? (
        <Text c="dimmed">No events recorded for this stream yet.</Text>
      ) : (
        <Timeline active={events.length - 1}>
          {events.map((event, i) => (
            <Timeline.Item key={i} title={String(event.event_type ?? `Event ${i + 1}`)}>
              <Text size="sm" c="dimmed">
                {JSON.stringify(event, null, 2).slice(0, 200)}
              </Text>
            </Timeline.Item>
          ))}
        </Timeline>
      )}
    </Stack>
  );
}
