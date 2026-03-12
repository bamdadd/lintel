import {
  Title,
  Stack,
  Paper,
  Text,
  SimpleGrid,
  Loader,
  Center,
  Alert,
  Group,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { IconAlertCircle, IconRefresh, IconShieldCheck } from '@tabler/icons-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { customInstance, ApiError } from '@/shared/api/client';

interface PiiStats {
  total_scanned: number;
  total_detected: number;
  total_anonymised: number;
  total_blocked: number;
  total_reveals: number;
}

const QUERY_KEY = ['pii', 'stats'];

function usePiiStats() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () =>
      customInstance<{ data: PiiStats; status: number }>(
        '/api/v1/pii/stats',
        { method: 'GET' },
      ).then((r) => r.data),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: (failureCount, error) =>
      failureCount < 3 &&
      !(error instanceof ApiError && (error.status === 403 || error.status === 404)),
  });
}

const statCards: { key: keyof PiiStats; label: string }[] = [
  { key: 'total_scanned', label: 'Messages Scanned' },
  { key: 'total_detected', label: 'PII Detected' },
  { key: 'total_anonymised', label: 'PII Anonymised' },
  { key: 'total_blocked', label: 'Messages Blocked' },
  { key: 'total_reveals', label: 'PII Reveals' },
];

function isEmptyStats(stats: PiiStats): boolean {
  return Object.values(stats).every((v) => v === 0);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return 'You do not have permission to view PII stats.';
    }
    if (error.status === 404) {
      return 'PII stats endpoint not found. The feature may not be enabled.';
    }
    return `Failed to load PII stats (HTTP ${error.status}). Please try again later.`;
  }
  return 'Failed to load PII stats. Please try again later.';
}

export function Component() {
  const { data: stats, isLoading, isError, error, isFetching } = usePiiStats();
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEY });
  };

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (isError) {
    return (
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={2}>PII Stats</Title>
          <Tooltip label="Refresh">
            <ActionIcon variant="subtle" onClick={handleRefresh} loading={isFetching}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {getErrorMessage(error)}
        </Alert>
      </Stack>
    );
  }

  if (!stats || isEmptyStats(stats)) {
    return (
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={2}>PII Stats</Title>
          <Tooltip label="Refresh">
            <ActionIcon variant="subtle" onClick={handleRefresh} loading={isFetching}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
        <Center py="xl">
          <Stack align="center" gap="xs">
            <IconShieldCheck size={48} color="var(--mantine-color-dimmed)" />
            <Text c="dimmed" size="lg">
              No PII scanning data yet
            </Text>
            <Text c="dimmed" size="sm">
              Stats will appear here once messages are scanned for PII.
            </Text>
          </Stack>
        </Center>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>PII Stats</Title>
        <Tooltip label="Refresh">
          <ActionIcon variant="subtle" onClick={handleRefresh} loading={isFetching}>
            <IconRefresh size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
        {statCards.map(({ key, label }) => (
          <Paper key={key} withBorder p="md" radius="md">
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
              {label}
            </Text>
            <Title order={2} mt="xs">
              {stats[key].toLocaleString()}
            </Title>
          </Paper>
        ))}
      </SimpleGrid>
    </Stack>
  );
}

Component.displayName = 'PiiStatsPage';
