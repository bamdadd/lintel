import { Group, Badge, Text, Paper } from '@mantine/core';
import {
  IconClock, IconLayersSubtract, IconFileText,
  IconMessageCircle, IconGitBranch, IconWebhook,
  IconClockHour4, IconUser, IconBriefcase, IconBolt,
} from '@tabler/icons-react';
import { getStatusColor } from '@/shared/components/StatusBadge';
import styles from './PipelineRunSummaryBar.module.css';

const TRIGGER_ICONS: Record<string, React.ElementType> = {
  chat: IconMessageCircle,
  slack_message: IconMessageCircle,
  git: IconGitBranch,
  pr_event: IconGitBranch,
  webhook: IconWebhook,
  schedule: IconClockHour4,
  manual: IconUser,
  work_item: IconBriefcase,
};

interface PipelineRunSummaryBarProps {
  status: string;
  triggerType?: string;
  createdAt?: string;
  stageCount: number;
  stagesPassed: number;
  stagesFailed: number;
  stagesRunning: number;
  artifactCount: number;
  totalDurationMs?: number;
}

function formatDuration(ms?: number): string {
  if (ms == null || ms <= 0) return '-';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function mapTriggerKind(triggerType?: string): string {
  if (!triggerType) return 'manual';
  if (triggerType.startsWith('chat')) return 'chat';
  if (triggerType.startsWith('work_item')) return 'work_item';
  if (triggerType.includes('git') || triggerType.includes('pr_event')) return 'git';
  if (triggerType.includes('webhook')) return 'webhook';
  if (triggerType.includes('schedule')) return 'schedule';
  if (triggerType.includes('slack')) return 'chat';
  return 'manual';
}

export function PipelineRunSummaryBar({
  status,
  triggerType,
  createdAt,
  stageCount,
  stagesPassed,
  stagesFailed,
  stagesRunning,
  artifactCount,
  totalDurationMs,
}: PipelineRunSummaryBarProps) {
  const triggerKind = mapTriggerKind(triggerType);
  const TriggerIcon = TRIGGER_ICONS[triggerKind] ?? IconBolt;

  return (
    <Paper className={styles.bar} withBorder radius="md" p="xs" px="md">
      <Group gap="lg" wrap="wrap">
        <Badge color={getStatusColor(status)} size="lg" variant="dot">
          {status?.replace(/_/g, ' ')}
        </Badge>

        <Group gap={6}>
          <TriggerIcon size={14} stroke={1.5} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">
            {triggerKind.replace(/_/g, ' ')}
          </Text>
          {createdAt && (
            <Text size="xs" c="dimmed">
              {new Date(createdAt).toLocaleString()}
            </Text>
          )}
        </Group>

        <Group gap={6}>
          <IconClock size={14} stroke={1.5} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">{formatDuration(totalDurationMs)}</Text>
        </Group>

        <Group gap={6}>
          <IconLayersSubtract size={14} stroke={1.5} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">
            {stageCount} stage{stageCount !== 1 ? 's' : ''}
          </Text>
          {stagesPassed > 0 && (
            <Badge size="xs" color="green" variant="light">{stagesPassed} passed</Badge>
          )}
          {stagesFailed > 0 && (
            <Badge size="xs" color="red" variant="light">{stagesFailed} failed</Badge>
          )}
          {stagesRunning > 0 && (
            <Badge size="xs" color="blue" variant="light">{stagesRunning} running</Badge>
          )}
        </Group>

        {artifactCount > 0 && (
          <Group gap={6}>
            <IconFileText size={14} stroke={1.5} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">
              {artifactCount} artifact{artifactCount !== 1 ? 's' : ''}
            </Text>
          </Group>
        )}
      </Group>
    </Paper>
  );
}
