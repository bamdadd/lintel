/**
 * StageCard — detailed view of a single pipeline stage.
 *
 * Extracted from PipelineDetailPage so it can be tested in isolation and
 * reused. Each data section (Logs, Implementation Plan, Outputs, Code Changes)
 * is wrapped in a <Collapsible> that defaults to collapsed, keeping the card
 * compact until the user explicitly expands a section.
 *
 * Sections are only rendered when the underlying data is present, so the card
 * stays clean for stages that don't produce every output type.
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import {
  Stack, Group, Text, Badge, Button, Paper, Code, ScrollArea,
} from '@mantine/core';
import {
  IconCheck, IconX, IconRefresh,
} from '@tabler/icons-react';
import { Collapsible } from '@/shared/components/Collapsible';
import { PlanView } from './PlanView';
import { StageReportEditor } from './StageReportEditor';
import { DiffView } from '@/shared/components/DiffView';
import { TimeAgo } from '@/shared/components/TimeAgo';
import { useNavigate } from 'react-router';

// ── Types ──────────────────────────────────────────────────────────────────

export interface StageItem {
  stage_id: string;
  name: string;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  stage_type?: string;
  outputs?: Record<string, unknown>;
  error?: string;
  logs?: string[];
  retry_count?: number;
}

interface StageCardProps {
  stage: StageItem;
  runId: string;
  /** Called after a successful approve/reject/retry so the parent can refetch. */
  onActionComplete?: () => void;
}

// ── Status colour map ──────────────────────────────────────────────────────

const statusColor: Record<string, string> = {
  pending: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
  skipped: 'gray',
  waiting_approval: 'yellow',
  approved: 'teal',
  rejected: 'red',
};

// ── Live-log hook (SSE) ────────────────────────────────────────────────────

function useStageLogs(
  runId: string | undefined,
  stageId: string | null,
  stageStatus: string | undefined,
) {
  const [lines, setLines] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId || !stageId || stageStatus !== 'running') {
      setLines([]);
      return;
    }

    const es = new EventSource(
      `/api/v1/pipelines/${runId}/stages/${stageId}/logs`,
    );

    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.type === 'log' && parsed.line) {
          setLines((prev) => [...prev, parsed.line]);
        } else if (parsed.type === 'error' && parsed.message) {
          setLines((prev) => [...prev, `ERROR: ${parsed.message}`]);
        } else if (parsed.type === 'end') {
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => es.close();

    return () => es.close();
  }, [runId, stageId, stageStatus]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines]);

  return { lines, scrollRef };
}

// ── Component ──────────────────────────────────────────────────────────────

export function StageCard({ stage, runId, onActionComplete }: StageCardProps) {
  const navigate = useNavigate();
  const [retrying, setRetrying] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  const { lines: logLines, scrollRef: logScrollRef } = useStageLogs(
    runId,
    stage.stage_id,
    stage.status,
  );

  // ── Action handlers ──────────────────────────────────────────────────────

  const handleRetry = useCallback(async () => {
    setRetrying(true);
    try {
      await fetch(
        `/api/v1/pipelines/${runId}/stages/${stage.stage_id}/retry`,
        { method: 'POST' },
      );
      onActionComplete?.();
    } finally {
      setRetrying(false);
    }
  }, [runId, stage.stage_id, onActionComplete]);

  const handleApprove = useCallback(async () => {
    setApproving(true);
    try {
      await fetch(
        `/api/v1/pipelines/${runId}/stages/${stage.stage_id}/approve`,
        { method: 'POST' },
      );
      onActionComplete?.();
    } finally {
      setApproving(false);
    }
  }, [runId, stage.stage_id, onActionComplete]);

  const handleReject = useCallback(async () => {
    setRejecting(true);
    try {
      await fetch(
        `/api/v1/pipelines/${runId}/stages/${stage.stage_id}/reject`,
        { method: 'POST' },
      );
      onActionComplete?.();
    } finally {
      setRejecting(false);
    }
  }, [runId, stage.stage_id, onActionComplete]);

  // ── Derived data ─────────────────────────────────────────────────────────

  // Logs: live SSE lines (running) or stored logs array (completed)
  const isRunning = stage.status === 'running';
  const liveLogsAvailable = isRunning && logLines.length > 0;
  const storedLogsAvailable =
    !isRunning && stage.logs != null && stage.logs.length > 0;
  const hasLogs = liveLogsAvailable || storedLogsAvailable;

  // Plan output
  const hasPlan = !!stage.outputs?.plan;

  // Research report (editable)
  const hasResearchReport = !!stage.outputs?.research_report;

  // Diff / code changes
  const hasDiff = !!stage.outputs?.diff;

  // Other outputs (everything except plan / research_report / diff / sandbox_id)
  const HIDDEN_OUTPUT_KEYS = new Set(['plan', 'research_report', 'diff', 'sandbox_id']);
  const otherOutputEntries = stage.outputs
    ? Object.entries(stage.outputs).filter(([k]) => !HIDDEN_OUTPUT_KEYS.has(k))
    : [];
  const hasOtherOutputs = otherOutputEntries.length > 0;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <Paper withBorder p="md" data-testid="stage-card">
      <Stack gap="sm">
        {/* ── Header ──────────────────────────────────────────────────── */}
        <Group justify="space-between">
          <Group gap="xs">
            <Text fw={600}>{stage.name}</Text>
            <Badge color={statusColor[stage.status] ?? 'gray'}>
              {stage.status}
            </Badge>
          </Group>

          <Group gap="xs">
            {stage.status === 'waiting_approval' && (
              <>
                <Button
                  variant="filled"
                  color="green"
                  size="compact-sm"
                  leftSection={<IconCheck size={14} />}
                  loading={approving}
                  onClick={handleApprove}
                  data-testid="approve-btn"
                >
                  Approve
                </Button>
                <Button
                  variant="light"
                  color="red"
                  size="compact-sm"
                  leftSection={<IconX size={14} />}
                  loading={rejecting}
                  onClick={handleReject}
                  data-testid="reject-btn"
                >
                  Reject
                </Button>
              </>
            )}
            {(stage.status === 'failed' || stage.status === 'running') && (
              <Button
                variant="light"
                size="compact-sm"
                leftSection={<IconRefresh size={14} />}
                loading={retrying}
                disabled={(stage.retry_count ?? 0) >= 3}
                onClick={handleRetry}
                data-testid="retry-btn"
              >
                {stage.status === 'failed' ? 'Retry' : 'Restart'}
                {(stage.retry_count ?? 0) > 0 &&
                  ` (${stage.retry_count}/3)`}
              </Button>
            )}
          </Group>
        </Group>

        {/* ── Meta ────────────────────────────────────────────────────── */}
        <Text size="sm" c="dimmed">
          Type: {stage.stage_type ?? '—'}
        </Text>
        <Group gap={4}>
          <Text size="sm">Started:</Text>
          <TimeAgo date={stage.started_at} size="sm" />
        </Group>
        <Group gap={4}>
          <Text size="sm">Finished:</Text>
          <TimeAgo date={stage.finished_at} size="sm" />
        </Group>
        {stage.duration_ms != null && (
          <Text size="sm">
            Duration: {(stage.duration_ms / 1000).toFixed(1)}s
          </Text>
        )}

        {/* ── Sandbox link ────────────────────────────────────────────── */}
        {!!stage.outputs?.sandbox_id && (
          <Group gap="xs">
            <Text size="sm">Sandbox:</Text>
            <Badge
              variant="light"
              size="lg"
              radius="sm"
              style={{ cursor: 'pointer' }}
              onClick={() =>
                navigate(`/sandboxes/${stage.outputs!.sandbox_id}`)
              }
            >
              {(stage.outputs.sandbox_id as string).slice(0, 12)}
            </Badge>
          </Group>
        )}

        {/* ── Error (always visible — not collapsible) ─────────────────── */}
        {stage.error && (
          <Paper
            withBorder
            p="sm"
            style={{ borderColor: 'var(--mantine-color-red-6)' }}
            data-testid="stage-error"
          >
            <Text size="sm" fw={600} c="red" mb={4}>
              Error
            </Text>
            <Text size="sm" c="red" style={{ whiteSpace: 'pre-wrap' }}>
              {stage.error}
            </Text>
          </Paper>
        )}

        {/* ── Collapsible: Logs ────────────────────────────────────────── */}
        {hasLogs && (
          <Collapsible
            title="Logs"
            defaultOpen={false}
            data-testid="section-logs"
          >
            <ScrollArea
              h={200}
              viewportRef={liveLogsAvailable ? logScrollRef : undefined}
              style={{
                backgroundColor: 'var(--mantine-color-dark-8)',
                borderRadius: 4,
              }}
            >
              <Code
                block
                style={{
                  backgroundColor: 'transparent',
                  whiteSpace: 'pre',
                  fontSize: 12,
                }}
              >
                {liveLogsAvailable
                  ? logLines.join('\n')
                  : (stage.logs ?? []).join('\n')}
              </Code>
            </ScrollArea>
          </Collapsible>
        )}

        {/* ── Collapsible: Research Report (editable) ──────────────────── */}
        {hasResearchReport && (
          <Collapsible
            title="Research Report"
            defaultOpen={false}
            data-testid="section-research"
          >
            <StageReportEditor
              runId={runId}
              stageId={stage.stage_id}
              stageName={stage.name}
              initialContent={stage.outputs!.research_report as string}
              status={stage.status}
            />
          </Collapsible>
        )}

        {/* ── Collapsible: Implementation Plan ─────────────────────────── */}
        {hasPlan && (
          <Collapsible
            title="Implementation Plan"
            defaultOpen={false}
            data-testid="section-plan"
          >
            <PlanView
              plan={
                stage.outputs!.plan as React.ComponentProps<
                  typeof PlanView
                >['plan']
              }
            />
          </Collapsible>
        )}

        {/* ── Collapsible: Code Changes ─────────────────────────────────── */}
        {hasDiff && (
          <Collapsible
            title="Code Changes"
            defaultOpen={false}
            data-testid="section-diff"
          >
            <DiffView content={stage.outputs!.diff as string} />
          </Collapsible>
        )}

        {/* ── Collapsible: Outputs ──────────────────────────────────────── */}
        {hasOtherOutputs && (
          <Collapsible
            title="Outputs"
            defaultOpen={false}
            data-testid="section-outputs"
          >
            <Code block style={{ fontSize: 12 }}>
              {JSON.stringify(
                Object.fromEntries(otherOutputEntries),
                null,
                2,
              )}
            </Code>
          </Collapsible>
        )}
      </Stack>
    </Paper>
  );
}
