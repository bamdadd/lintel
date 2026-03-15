import { useState, useEffect } from 'react';
import { Title, Stack, SimpleGrid, Center, Loader } from '@mantine/core';
import { TelegramConnectionCard } from './TelegramConnectionCard';
import { listChannelConnections } from './channelsApi';
import type { ChannelConnection } from './channelsApi';

export function Component() {
  const [connections, setConnections] = useState<ChannelConnection[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchConnections = async () => {
    try {
      const data = await listChannelConnections();
      setConnections(data);
    } catch {
      // Silent fail — show empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchConnections();
  }, []);

  if (loading) return <Center py="xl"><Loader /></Center>;

  const telegram = connections.find((c) => c.channel_type === 'telegram') ?? {
    channel_type: 'telegram',
    connected: false,
    bot_username: '',
  };

  return (
    <Stack gap="md">
      <Title order={2}>Channel Connections</Title>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <TelegramConnectionCard
          connection={telegram}
          onUpdate={() => void fetchConnections()}
        />
      </SimpleGrid>
    </Stack>
  );
}
