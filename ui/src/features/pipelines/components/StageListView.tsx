/**
 * StageListView — GitHub Actions-style stage list with expand/collapse rows.
 *
 * Each row shows: chevron | status icon | stage name | duration
 * Expanding a row reveals the StageCard detail view inline.
 */

import {
  UnstyledButton, Group, Text, Collapse, Box, Loader,
} from '@mantine/core';
import {
  IconChevronRight,
  IconCircleCheck,
  IconCircleX,
  IconCircle,
  IconPlayerPause,
  IconCircleDashed,
} from '@tabler/icons-react';
import { StageCard } from './StageCard';
import type { StageItem } from './StageCard';

interface StageListViewProps {
  stages: StageItem[];
  runId: string;
  /** Controlled: which stage is currently expanded */
  selectedStageId?: string | null;
  /** Controlled: callback when a stage row is clicked */
  onStageSelect?: (stageId: string | null) => void;
  onActionComplete?: () => void;
}

const statusIcon: Record<string, { icon: React.ElementType; color: string }> = {
  succeeded: { icon: IconCircleCheck, color: 'var(--mantine-color-green-6)' },
  approved: { icon: IconCircleCheck, color: 'var(--mantine-color-teal-6)' },
  failed: { icon: IconCircleX, color: 'var(--mantine-color-red-6)' },
  rejected: { icon: IconCircleX, color: 'var(--mantine-color-red-6)' },
  cancelled: { icon: IconCircleX, color: 'var(--mantine-color-orange-6)' },
  running: { icon: Loader, color: 'var(--mantine-color-blue-6)' },
  waiting_approval: { icon: IconPlayerPause, color: 'var(--mantine-color-yellow-6)' },
  skipped: { icon: IconCircleDashed, color: 'var(--mantine-color-gray-6)' },
  pending: { icon: IconCircle, color: 'var(--mantine-color-gray-6)' },
};

function formatDuration(ms: number | undefined): string {
  if (ms == null) return '';
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function StatusIcon({ status }: { status: string }) {
  const entry = statusIcon[status] ?? statusIcon.pending!;
  if (status === 'running') {
    return <Loader size={18} color={entry.color} type="oval" />;
  }
  const Icon = entry.icon;
  return <Icon size={18} color={entry.color} stroke={1.5} />;
}

export function StageListView({
  stages,
  runId,
  selectedStageId,
  onStageSelect,
  onActionComplete,
}: StageListViewProps) {
  const toggle = (stageId: string) => {
    if (onStageSelect) {
      onStageSelect(selectedStageId === stageId ? null : stageId);
    }
  };

  return (
    <Box>
      {stages.map((stage) => {
        const isExpanded = selectedStageId === stage.stage_id;
        const hasDuration = stage.duration_ms != null && stage.duration_ms > 0;
        const isExpandable = stage.status !== 'pending';

        return (
          <Box
            key={stage.stage_id}
            style={(theme) => ({
              borderBottom: `1px solid ${theme.colors.dark[5]}`,
            })}
          >
            <UnstyledButton
              onClick={() => {
                if (isExpandable) toggle(stage.stage_id);
              }}
              style={{
                width: '100%',
                cursor: isExpandable ? 'pointer' : 'default',
              }}
              py="sm"
              px="xs"
            >
              <Group justify="space-between" wrap="nowrap">
                <Group gap="md" wrap="nowrap">
                  <IconChevronRight
                    size={14}
                    stroke={2}
                    style={{
                      transition: 'transform 200ms ease',
                      transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                      opacity: isExpandable ? 0.7 : 0,
                      flexShrink: 0,
                    }}
                  />
                  <StatusIcon status={stage.status} />
                  <Text size="sm" fw={isExpanded ? 600 : 400}>
                    {stage.name}
                  </Text>
                </Group>
                {hasDuration && (
                  <Text size="sm" c="dimmed" style={{ flexShrink: 0 }}>
                    {formatDuration(stage.duration_ms)}
                  </Text>
                )}
              </Group>
            </UnstyledButton>

            <Collapse in={isExpanded}>
              <Box
                py="md"
                px="lg"
                ml={46}
                style={(theme) => ({
                  borderLeft: `2px solid ${theme.colors.dark[4]}`,
                })}
              >
                <StageCard
                  stage={stage}
                  runId={runId}
                  onActionComplete={onActionComplete}
                />
              </Box>
            </Collapse>
          </Box>
        );
      })}
    </Box>
  );
}
