import { useState, useEffect } from 'react';
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
  timed_out: 'var(--mantine-color-orange-5)',
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

function formatElapsed(startedAt: string): string {
  const elapsed = Date.now() - new Date(startedAt).getTime();
  return formatDuration(elapsed);
}

function stageTooltip(stage: PipelineStage, _tick: number): string {
  const base = `${stage.name}: ${stage.status}`;
  // For running stages, always show live elapsed time
  if (stage.status === 'running' && stage.started_at) {
    return `${base} (${formatElapsed(stage.started_at)} so far)`;
  }
  // For completed stages, show final duration (skip 0/null)
  if (stage.duration_ms) {
    return `${base} (${formatDuration(stage.duration_ms)})`;
  }
  // Fallback: if finished but no duration_ms, calculate from timestamps
  if (stage.started_at && stage.finished_at) {
    const ms = new Date(stage.finished_at).getTime() - new Date(stage.started_at).getTime();
    if (ms > 0) return `${base} (${formatDuration(ms)})`;
  }
  return base;
}

interface PipelineStageIndicatorProps {
  pipeline: PipelineRun;
  stages: PipelineStage[];
}

export function PipelineStageIndicator({ pipeline, stages }: PipelineStageIndicatorProps) {
  const navigate = useNavigate();
  const hasRunning = stages.some((s) => s.status === 'running');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!hasRunning) return;
    const id = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(id);
  }, [hasRunning]);

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
            label={stageTooltip(stage, tick)}
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
