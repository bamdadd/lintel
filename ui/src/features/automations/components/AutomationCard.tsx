import { ActionIcon, Badge, Group, Paper, Switch, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';

import {
  useAutomationsTriggerAutomation,
  useAutomationsUpdateAutomation,
} from '@/generated/api/automations/automations';

interface AutomationCardProps {
  automation: {
    automation_id: string;
    name: string;
    project_id: string;
    trigger_type: string;
    trigger_config: Record<string, unknown>;
    concurrency_policy: string;
    enabled: boolean;
  };
  lastRunStatus?: 'completed' | 'failed' | null;
  lastRunTime?: string | null;
}

const triggerColors: Record<string, string> = {
  cron: 'violet',
  event: 'blue',
  manual: 'gray',
};

function getBorderColor(enabled: boolean, lastRunStatus?: string | null): string {
  if (!enabled) return 'var(--mantine-color-dark-4)';
  if (lastRunStatus === 'completed') return 'var(--mantine-color-green-6)';
  if (lastRunStatus === 'failed') return 'var(--mantine-color-red-6)';
  return 'var(--mantine-color-dark-4)';
}

function getTriggerPreview(triggerType: string, config: Record<string, unknown>): string {
  if (triggerType === 'cron') return String(config.schedule ?? '');
  if (triggerType === 'event') {
    const types = config.event_types;
    if (Array.isArray(types)) return types.join(', ');
  }
  return 'On demand';
}

export function AutomationCard({ automation, lastRunStatus, lastRunTime }: AutomationCardProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const updateMut = useAutomationsUpdateAutomation();
  const triggerMut = useAutomationsTriggerAutomation();

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    updateMut.mutate(
      { automationId: automation.automation_id, data: { enabled: !automation.enabled } },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
        },
      },
    );
  };

  const handleTrigger = (e: React.MouseEvent) => {
    e.stopPropagation();
    triggerMut.mutate(
      { automationId: automation.automation_id },
      {
        onSuccess: () => {
          notifications.show({ title: 'Triggered', message: `${automation.name} fired`, color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to trigger automation', color: 'red' });
        },
      },
    );
  };

  return (
    <Paper
      p="md"
      radius="md"
      withBorder
      style={{
        borderLeftWidth: 3,
        borderLeftColor: getBorderColor(automation.enabled, lastRunStatus),
        cursor: 'pointer',
        opacity: automation.enabled ? 1 : 0.6,
      }}
      onClick={() => navigate(`/automations/${automation.automation_id}`)}
    >
      <Group justify="space-between" align="start" mb="xs">
        <Text fw={500} size="sm">{automation.name}</Text>
        <Group gap="xs">
          {automation.trigger_type === 'manual' && (
            <ActionIcon size="sm" variant="subtle" onClick={handleTrigger} title="Trigger now">
              <IconPlayerPlay size={14} />
            </ActionIcon>
          )}
          <Switch
            size="xs"
            checked={automation.enabled}
            onClick={handleToggle}
            onChange={() => {}}
          />
        </Group>
      </Group>
      <Text size="xs" c="dimmed" mb="xs">{automation.project_id}</Text>
      <Group gap="xs" mb="xs">
        <Badge size="xs" color={triggerColors[automation.trigger_type] ?? 'gray'}>
          {automation.trigger_type}
        </Badge>
        <Text size="xs" c="dimmed" ff="monospace">
          {getTriggerPreview(automation.trigger_type, automation.trigger_config)}
        </Text>
      </Group>
      {lastRunTime ? (
        <Text size="xs" c={lastRunStatus === 'failed' ? 'red' : 'green'}>
          Last run: {lastRunTime} {lastRunStatus === 'completed' ? '\u2713' : '\u2717'}
        </Text>
      ) : (
        <Text size="xs" c="dimmed">No runs yet</Text>
      )}
    </Paper>
  );
}
