import { Badge, Group, Tooltip, ActionIcon } from '@mantine/core';
import { IconKey, IconRefresh } from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

interface CredentialsStatus {
  configured: boolean;
  status?: 'valid' | 'expired' | 'missing' | 'invalid';
  expires_at?: string;
  minutes_remaining?: number;
  detail?: string;
}

export function ClaudeCredentialsBanner() {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['claude-credentials-status'],
    queryFn: () =>
      customInstance<{ data: CredentialsStatus }>('/api/v1/admin/claude-credentials-status'),
    refetchInterval: 60_000,
    retry: 1,
  });

  const refresh = useMutation({
    mutationFn: () =>
      customInstance('/api/v1/admin/refresh-claude-credentials', { method: 'POST' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['claude-credentials-status'] });
    },
  });

  const status = data?.data;
  if (!status?.configured) return null;

  const isWarning = status.status === 'valid' && (status.minutes_remaining ?? 999) < 30;
  const isError = status.status === 'expired' || status.status === 'missing' || status.status === 'invalid';

  const color = isError ? 'red' : isWarning ? 'yellow' : 'green';
  const label = isError
    ? `Claude Code credentials ${status.status}`
    : isWarning
      ? `Claude Code token expires in ${status.minutes_remaining}m`
      : `Claude Code token valid (${status.minutes_remaining}m remaining)`;

  return (
    <Tooltip label={label}>
      <Group gap={4}>
        <Badge size="sm" color={color} variant="light" leftSection={<IconKey size={12} />}>
          {isError ? status.status : `${status.minutes_remaining ?? '?'}m`}
        </Badge>
        <ActionIcon
          size="xs"
          variant="subtle"
          color={color}
          onClick={() => refresh.mutate()}
          loading={refresh.isPending}
          aria-label="Refresh Claude credentials"
        >
          <IconRefresh size={12} />
        </ActionIcon>
      </Group>
    </Tooltip>
  );
}
