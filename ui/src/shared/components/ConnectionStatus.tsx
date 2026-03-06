import { Badge, Group, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

export function ConnectionStatus() {
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => customInstance<{ data: { status: string } }>('/healthz'),
    refetchInterval: 30_000,
    retry: 1,
  });

  const connected = !isError && data?.data?.status === 'ok';

  return (
    <Tooltip label={connected ? 'API connected' : 'API unreachable'}>
      <Group gap={6}>
        <Badge
          size="xs"
          circle
          color={connected ? 'green' : 'red'}
          variant="filled"
        />
      </Group>
    </Tooltip>
  );
}
