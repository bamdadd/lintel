import { useState } from 'react';
import { Badge, Group, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { customInstance, ApiError } from '@/shared/api/client';

export function ConnectionStatus() {
  const { data, isError, error, failureCount } = useQuery({
    queryKey: ['health'],
    queryFn: () => customInstance<{ data: { status: string } }>('/healthz'),
    refetchInterval: 30_000,
    retry: 1,
  });

  const connected = !isError && data?.data?.status === 'ok';

  const errorDetail = isError
    ? error instanceof ApiError
      ? `${error.status}: ${error.detail}`
      : error instanceof TypeError
        ? `Network error — cannot reach API`
        : `${error?.message ?? 'Unknown error'}`
    : null;

  const baseUrl = typeof window !== 'undefined'
    && window.location.hostname !== 'localhost'
    && window.location.hostname !== '127.0.0.1'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : '';
  const tooltip = connected
    ? `API connected → ${baseUrl || 'proxy'}`
    : `Fetch: ${baseUrl}/healthz — ${errorDetail} (${failureCount} attempts)`;

  const [showDetail, setShowDetail] = useState(false);

  return (
    <div>
      <Group gap={6} onClick={() => setShowDetail((v) => !v)} style={{ cursor: 'pointer' }}>
        <Badge
          size="xs"
          circle
          color={connected ? 'green' : 'red'}
          variant="filled"
        />
        <Text size="xs" c={connected ? 'dimmed' : 'red'}>
          {connected ? 'Connected' : 'Disconnected'}
        </Text>
      </Group>
      {showDetail && (
        <Text size="xs" c="dimmed" mt={4} style={{ maxWidth: 300, wordBreak: 'break-all' }}>
          {tooltip}
        </Text>
      )}
    </div>
  );
}
