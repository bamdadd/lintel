import { Badge, Group, Text, Tooltip } from '@mantine/core';
import { IconCircleFilled, IconTool } from '@tabler/icons-react';

export type HealthStatus = 'connected' | 'disconnected' | 'checking';

interface HealthStatusBadgeProps {
  status: HealthStatus;
  toolCount: number | null;
  lastChecked: Date | null;
}

function formatLastChecked(date: Date | null): string {
  if (!date) return 'Never';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  return `${diffHr}h ago`;
}

const STATUS_CONFIG: Record<HealthStatus, { color: string; label: string }> = {
  connected: { color: 'green', label: 'Connected' },
  disconnected: { color: 'red', label: 'Disconnected' },
  checking: { color: 'yellow', label: 'Checking...' },
};

export function HealthStatusBadge({ status, toolCount, lastChecked }: HealthStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <Tooltip label={`Last checked: ${formatLastChecked(lastChecked)}`} withArrow>
      <Group gap={8} wrap="nowrap">
        <Badge
          color={config.color}
          variant="light"
          leftSection={<IconCircleFilled size={8} />}
        >
          {config.label}
        </Badge>
        {toolCount !== null && (
          <Badge
            color="blue"
            variant="light"
            size="sm"
            leftSection={<IconTool size={10} />}
          >
            <Text span size="xs">{toolCount}</Text>
          </Badge>
        )}
      </Group>
    </Tooltip>
  );
}
