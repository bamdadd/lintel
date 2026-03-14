import { Group, Tooltip, Box, Text } from '@mantine/core';
import { useNavigate } from 'react-router';
import type { PipelineRun, PipelineStage } from '../api';

const STATUS_COLOR: Record<string, string> = {
  pending: 'var(--mantine-color-dark-3)',
  running: 'var(--mantine-color-blue-5)',
  succeeded: 'var(--mantine-color-green-6)',
  failed: 'var(--mantine-color-red-6)',
  skipped: 'var(--mantine-color-gray-5)',
  waiting_approval: 'var(--mantine-color-yellow-5)',
  approved: 'var(--mantine-color-green-4)',
  rejected: 'var(--mantine-color-red-4)',
};

interface PipelineStageIndicatorProps {
  pipeline: PipelineRun;
  stages: PipelineStage[];
}

export function PipelineStageIndicator({ pipeline, stages }: PipelineStageIndicatorProps) {
  const navigate = useNavigate();

  if (stages.length === 0) return null;

  return (
    <Tooltip.Group>
      <Group
        gap={3}
        wrap="nowrap"
        mt={4}
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          navigate(`/pipelines/${pipeline.run_id}`);
        }}
      >
        {stages.map((stage) => (
          <Tooltip
            key={stage.stage_id}
            label={`${stage.name}: ${stage.status}`}
            withArrow
            position="top"
          >
            <Box
              style={{
                width: 14,
                height: 14,
                borderRadius: 2,
                backgroundColor: STATUS_COLOR[stage.status] ?? 'var(--mantine-color-dark-3)',
                transition: 'transform 100ms ease',
                animation: stage.status === 'running' ? 'pulse-stage 1.5s ease-in-out infinite' : undefined,
              }}
            />
          </Tooltip>
        ))}
        <Text size="xs" c="dimmed" ml={2} style={{ whiteSpace: 'nowrap' }}>
          {pipeline.status}
        </Text>
      </Group>
      <style>{`
        @keyframes pulse-stage {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </Tooltip.Group>
  );
}
