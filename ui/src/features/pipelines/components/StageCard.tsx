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
  Modal, ActionIcon, Tooltip, TypographyStylesProvider, UnstyledButton,
  useMantineColorScheme,
} from '@mantine/core';
import {
  IconCheck, IconX, IconRefresh, IconMaximize,
  IconTerminal, IconFileText, IconListCheck, IconGitMerge, IconEye, IconDatabase,
} from '@tabler/icons-react';
import { Collapsible } from '@/shared/components/Collapsible';
import { PlanView } from './PlanView';
import { StageReportEditor } from './StageReportEditor';
import { DiffView } from '@/shared/components/DiffView';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../../chat/chat-markdown.css';
import { TimeAgo } from '@/shared/components/TimeAgo';
import { getStatusColor } from '@/shared/components/StatusBadge';
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
  attempts?: Array<{
    attempt: number;
    status: string;
    inputs?: Record<string, unknown>;
    outputs?: Record<string, unknown>;
    error?: string;
    duration_ms?: number;
    started_at?: string;
    finished_at?: string;
    logs?: string[];
  }>;
}

interface StageCardProps {
  stage: StageItem;
  runId: string;
  /** All stages in the pipeline — used by the fullscreen modal to aggregate artifacts. */
  allStages?: StageItem[];
  /** Called after a successful approve/reject/retry so the parent can refetch. */
  onActionComplete?: () => void;
}

// ── Live-log hook (SSE) ────────────────────────────────────────────────────

function useStageLogs(
  runId: string | undefined,
  stageId: string | null,
  stageStatus: string | undefined,
) {
  const [lines, setLines] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const modalScrollRef = useRef<HTMLDivElement>(null);

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
    if (modalScrollRef.current) {
      modalScrollRef.current.scrollTop = modalScrollRef.current.scrollHeight;
    }
  }, [lines]);

  return { lines, scrollRef, modalScrollRef };
}

// ── Tab config ─────────────────────────────────────────────────────────────

type FullscreenTab = 'logs' | 'research' | 'plan' | 'diff' | 'review' | 'outputs';

const TAB_META: Record<FullscreenTab, { label: string; icon: typeof IconTerminal }> = {
  logs:     { label: 'Logs',              icon: IconTerminal },
  research: { label: 'Research Report',   icon: IconFileText },
  plan:     { label: 'Implementation Plan', icon: IconListCheck },
  diff:     { label: 'Code Changes',      icon: IconGitMerge },
  review:   { label: 'Review',            icon: IconEye },
  outputs:  { label: 'Outputs',           icon: IconDatabase },
};

// ── Fullscreen modal (aggregates artifacts from all pipeline stages) ───────

const HIDDEN_KEYS = new Set(['plan', 'research_report', 'diff', 'sandbox_id', 'review', 'pr_url']);

interface ArtifactTab {
  key: string;          // unique key for React
  type: FullscreenTab;  // which renderer to use
  label: string;        // display label
  stageName: string;    // originating stage name
  stage: StageItem;     // originating stage
}

function buildArtifactTabs(
  allStages: StageItem[],
  currentStage: StageItem,
  liveLogsAvailable: boolean,
): ArtifactTab[] {
  const tabs: ArtifactTab[] = [];
  const multi = allStages.length > 1;

  for (const s of allStages) {
    // Logs: live SSE for current stage, stored logs for others
    const isCurrentStage = s.stage_id === currentStage.stage_id;
    const hasLogs = isCurrentStage
      ? (liveLogsAvailable || (s.logs != null && s.logs.length > 0))
      : (s.logs != null && s.logs.length > 0);
    if (hasLogs) {
      tabs.push({
        key: `logs:${s.stage_id}`,
        type: 'logs',
        label: multi ? `Logs — ${s.name}` : 'Logs',
        stageName: s.name,
        stage: s,
      });
    }

    if (s.outputs?.research_report) {
      tabs.push({
        key: `research:${s.stage_id}`,
        type: 'research',
        label: multi ? `Research — ${s.name}` : 'Research Report',
        stageName: s.name,
        stage: s,
      });
    }
    if (s.outputs?.plan) {
      tabs.push({
        key: `plan:${s.stage_id}`,
        type: 'plan',
        label: multi ? `Plan — ${s.name}` : 'Implementation Plan',
        stageName: s.name,
        stage: s,
      });
    }
    if (s.outputs?.diff) {
      tabs.push({
        key: `diff:${s.stage_id}`,
        type: 'diff',
        label: multi ? `Diff — ${s.name}` : 'Code Changes',
        stageName: s.name,
        stage: s,
      });
    }
    if (s.outputs?.review) {
      tabs.push({
        key: `review:${s.stage_id}`,
        type: 'review',
        label: multi ? `Review — ${s.name}` : 'Review',
        stageName: s.name,
        stage: s,
      });
    }
    const otherEntries = s.outputs
      ? Object.entries(s.outputs).filter(([k]) => !HIDDEN_KEYS.has(k))
      : [];
    if (otherEntries.length > 0) {
      tabs.push({
        key: `outputs:${s.stage_id}`,
        type: 'outputs',
        label: multi ? `Outputs — ${s.name}` : 'Outputs',
        stageName: s.name,
        stage: s,
      });
    }
  }

  return tabs;
}

/** Group artifact tabs by stage_id, preserving stage order. */
function groupTabsByStage(tabs: ArtifactTab[], allStages: StageItem[]) {
  const map = new Map<string, ArtifactTab[]>();
  for (const tab of tabs) {
    const list = map.get(tab.stage.stage_id) ?? [];
    list.push(tab);
    map.set(tab.stage.stage_id, list);
  }
  // Return in pipeline stage order, skipping stages with no artifacts
  return allStages
    .filter((s) => map.has(s.stage_id))
    .map((s) => ({ stage: s, tabs: map.get(s.stage_id)! }));
}

export function StageFullscreenModal({
  opened, onClose, initialTabKey, allStages, currentStage,
  logLines = [], liveLogsAvailable = false, logModalScrollRef, onTabChange,
}: {
  opened: boolean;
  onClose: () => void;
  initialTabKey?: string;
  onTabChange?: (tabKey: string) => void;
  allStages: StageItem[];
  currentStage?: StageItem;
  logLines?: string[];
  liveLogsAvailable?: boolean;
  logModalScrollRef?: React.RefObject<HTMLDivElement | null>;
}) {
  const { colorScheme } = useMantineColorScheme();
  const resolvedCurrentStage = currentStage ?? allStages[0]!;
  const [activeKey, setActiveKeyRaw] = useState(initialTabKey ?? '');
  const setActiveKey = useCallback((key: string) => {
    setActiveKeyRaw(key);
    onTabChange?.(key);
  }, [onTabChange]);

  useEffect(() => {
    if (opened && initialTabKey) setActiveKeyRaw(initialTabKey);
  }, [initialTabKey, opened]);

  const artifactTabs = buildArtifactTabs(allStages, resolvedCurrentStage, liveLogsAvailable);
  const grouped = groupTabsByStage(artifactTabs, allStages);

  const activeTab = artifactTabs.find((t) => t.key === activeKey) ?? artifactTabs[0];
  const isDark = colorScheme === 'dark';
  const borderColor = isDark ? 'var(--mantine-color-dark-4)' : 'var(--mantine-color-gray-3)';

  if (!activeTab) return null;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      fullScreen
      title={
        <Group gap="sm">
          <Text fw={600}>Pipeline Artifacts</Text>
          <Badge variant="light" size="sm">
            {allStages.length} stage{allStages.length !== 1 ? 's' : ''}
          </Badge>
        </Group>
      }
      styles={{
        body: { padding: 0, display: 'flex', height: 'calc(100vh - 60px)' },
        header: { borderBottom: `1px solid ${borderColor}` },
      }}
    >
      {/* ── Sidebar: stages + their artifact links ─────────────────── */}
      <ScrollArea
        style={{
          width: 220,
          flexShrink: 0,
          borderRight: `1px solid ${borderColor}`,
        }}
        offsetScrollbars
      >
        <Stack gap={0}>
          {grouped.map(({ stage: s, tabs }) => {
            const isActiveStage = activeTab.stage.stage_id === s.stage_id;
            return (
              <div key={s.stage_id}>
                {/* Stage header */}
                <Group
                  gap={6}
                  px="sm"
                  py={6}
                  wrap="nowrap"
                  style={{
                    backgroundColor: isActiveStage
                      ? (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)')
                      : 'transparent',
                  }}
                >
                  <Badge
                    size="xs"
                    variant="dot"
                    color={getStatusColor(s.status)}
                    style={{ flexShrink: 0 }}
                  >
                    {s.name}
                  </Badge>
                </Group>

                {/* Artifact links for this stage */}
                {tabs.map((tab) => {
                  const meta = TAB_META[tab.type];
                  const Icon = meta.icon;
                  const isActive = tab.key === activeTab.key;
                  return (
                    <UnstyledButton
                      key={tab.key}
                      onClick={() => setActiveKey(tab.key)}
                      px="sm"
                      py={5}
                      pl={28}
                      style={{
                        display: 'block',
                        width: '100%',
                        borderLeft: isActive
                          ? '2px solid var(--mantine-color-blue-5)'
                          : '2px solid transparent',
                        backgroundColor: isActive
                          ? (isDark ? 'var(--mantine-color-dark-5)' : 'var(--mantine-color-gray-1)')
                          : 'transparent',
                      }}
                    >
                      <Group gap={6} wrap="nowrap">
                        <Icon size={13} style={{ opacity: 0.6, flexShrink: 0 }} />
                        <Text size="xs" fw={isActive ? 600 : 400} truncate>
                          {meta.label}
                        </Text>
                      </Group>
                    </UnstyledButton>
                  );
                })}
              </div>
            );
          })}
        </Stack>
      </ScrollArea>

      {/* ── Content area ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Content header */}
        <Group
          px="md"
          py={8}
          style={{ borderBottom: `1px solid ${borderColor}`, flexShrink: 0 }}
        >
          <Badge size="xs" variant="dot" color={getStatusColor(activeTab.stage.status)}>
            {activeTab.stage.name}
          </Badge>
          <Text size="sm" fw={600}>{TAB_META[activeTab.type].label}</Text>
        </Group>

        {/* Content body */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {activeTab.type === 'logs' && (() => {
            const isLive = liveLogsAvailable && activeTab.stage.stage_id === resolvedCurrentStage.stage_id;
            return (
              <ScrollArea
                style={{ flex: 1 }}
                viewportRef={isLive ? logModalScrollRef : undefined}
                offsetScrollbars
              >
                <Code
                  block
                  style={{
                    backgroundColor: 'var(--mantine-color-dark-8)',
                    whiteSpace: 'pre',
                    fontSize: 12,
                    minHeight: '100%',
                  }}
                >
                  {isLive
                    ? logLines.join('\n')
                    : (activeTab.stage.logs ?? []).join('\n')}
                </Code>
              </ScrollArea>
            );
          })()}

          {activeTab.type === 'research' && (
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <div style={{ padding: 'var(--mantine-spacing-xl)' }}>
                <TypographyStylesProvider>
                  <div className="chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {(activeTab.stage.outputs?.research_report as string) ?? ''}
                    </ReactMarkdown>
                  </div>
                </TypographyStylesProvider>
              </div>
            </ScrollArea>
          )}

          {activeTab.type === 'plan' && (
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <div style={{ padding: 'var(--mantine-spacing-xl)' }}>
                <PlanView
                  plan={
                    activeTab.stage.outputs?.plan as React.ComponentProps<
                      typeof PlanView
                    >['plan']
                  }
                />
              </div>
            </ScrollArea>
          )}

          {activeTab.type === 'diff' && (
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <div style={{ padding: 'var(--mantine-spacing-xl)' }}>
                <DiffView content={activeTab.stage.outputs!.diff as string} />
              </div>
            </ScrollArea>
          )}

          {activeTab.type === 'review' && (
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <div style={{ padding: 'var(--mantine-spacing-xl)' }}>
                <TypographyStylesProvider>
                  <div className="chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {(activeTab.stage.outputs?.review as string) ?? ''}
                    </ReactMarkdown>
                  </div>
                </TypographyStylesProvider>
              </div>
            </ScrollArea>
          )}

          {activeTab.type === 'outputs' && (
            <ScrollArea style={{ flex: 1 }} offsetScrollbars>
              <div style={{ padding: 'var(--mantine-spacing-xl)' }}>
                <Code block style={{ fontSize: 12 }}>
                  {JSON.stringify(
                    Object.fromEntries(
                      Object.entries(activeTab.stage.outputs ?? {}).filter(
                        ([k]) => !HIDDEN_KEYS.has(k),
                      ),
                    ),
                    null,
                    2,
                  )}
                </Code>
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    </Modal>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export function StageCard({ stage, runId, allStages, onActionComplete }: StageCardProps) {
  const navigate = useNavigate();
  const [retrying, setRetrying] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [fullscreenOpen, setFullscreenOpen] = useState(false);
  const [fullscreenTabKey, setFullscreenTabKey] = useState('');

  const openFullscreen = useCallback((type: FullscreenTab) => {
    setFullscreenTabKey(`${type}:${stage.stage_id}`);
    setFullscreenOpen(true);
  }, [stage.stage_id]);

  const { lines: logLines, scrollRef: logScrollRef, modalScrollRef: logModalScrollRef } = useStageLogs(
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

  // Review text
  const hasReview = !!stage.outputs?.review;

  // Diff / code changes
  const hasDiff = !!stage.outputs?.diff;

  // Other outputs (everything except plan / research_report / diff / sandbox_id / review)
  const HIDDEN_OUTPUT_KEYS = new Set(['plan', 'research_report', 'diff', 'sandbox_id', 'review', 'pr_url']);
  const otherOutputEntries = stage.outputs
    ? Object.entries(stage.outputs).filter(([k]) => !HIDDEN_OUTPUT_KEYS.has(k))
    : [];
  const hasOtherOutputs = otherOutputEntries.length > 0;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <Stack gap="sm" data-testid="stage-card">
        {/* ── Actions ─────────────────────────────────────────────────── */}
        <Group justify="flex-end" gap="xs">
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
                disabled={(stage.retry_count ?? 0) >= 5}
                onClick={handleRetry}
                data-testid="retry-btn"
              >
                {stage.status === 'failed' ? 'Retry' : 'Restart'}
                {(stage.retry_count ?? 0) > 0 &&
                  ` (${stage.retry_count}/5)`}
              </Button>
            )}
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

        {/* ── PR link ────────────────────────────────────────────────── */}
        {!!stage.outputs?.pr_url && (
          <Group gap="xs">
            <Text size="sm">Pull Request:</Text>
            <Button
              component="a"
              href={stage.outputs.pr_url as string}
              target="_blank"
              rel="noopener noreferrer"
              variant="light"
              size="compact-sm"
              data-testid="pr-link"
            >
              {(stage.outputs.pr_url as string).replace(/^https?:\/\/github\.com\//, '')}
            </Button>
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
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('logs'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
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
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('research'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
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
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('plan'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
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
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('diff'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
          >
            <DiffView content={stage.outputs!.diff as string} />
          </Collapsible>
        )}

        {/* ── Collapsible: Review ──────────────────────────────────────── */}
        {hasReview && (
          <Collapsible
            title={`Review — ${stage.outputs?.verdict === 'approve' ? '✅ Approved' : '⚠️ Changes Requested'}`}
            defaultOpen={stage.outputs?.verdict !== 'approve'}
            data-testid="section-review"
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('review'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
          >
            <Paper p="sm" withBorder>
              <ScrollArea.Autosize mah={400}>
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {stage.outputs!.review as string}
                  </ReactMarkdown>
                </div>
              </ScrollArea.Autosize>
            </Paper>
          </Collapsible>
        )}

        {/* ── Collapsible: Outputs ──────────────────────────────────────── */}
        {hasOtherOutputs && (
          <Collapsible
            title="Outputs"
            defaultOpen={false}
            data-testid="section-outputs"
            badge={
              <Tooltip label="Fullscreen">
                <ActionIcon
                  variant="subtle"
                  size="xs"
                  onClick={(e) => { e.stopPropagation(); openFullscreen('outputs'); }}
                >
                  <IconMaximize size={14} />
                </ActionIcon>
              </Tooltip>
            }
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

        {/* ── Collapsible: Previous Attempts ─────────────────────────────── */}
        {(stage.attempts?.length ?? 0) > 0 && (
          <Collapsible
            title={`Previous Attempts (${stage.attempts!.length})`}
            defaultOpen={false}
            data-testid="section-attempts"
          >
            <Stack gap="xs">
              {stage.attempts!.map((att) => (
                <Paper key={att.attempt} withBorder p="xs">
                  <Group justify="space-between" mb={4}>
                    <Text size="sm" fw={600}>
                      Attempt {att.attempt}
                    </Text>
                    <Badge
                      size="sm"
                      color={getStatusColor(att.status)}
                    >
                      {att.status}
                    </Badge>
                  </Group>
                  {att.duration_ms != null && (
                    <Text size="xs" c="dimmed">
                      Duration: {(att.duration_ms / 1000).toFixed(1)}s
                    </Text>
                  )}
                  {att.error && (
                    <Text size="xs" c="red" mt={4}>
                      {att.error}
                    </Text>
                  )}
                  {att.logs && att.logs.length > 0 && (
                    <Collapsible title="Logs" defaultOpen={false}>
                      <ScrollArea h={120}>
                        <Code
                          block
                          style={{ fontSize: 11, backgroundColor: 'var(--mantine-color-dark-8)' }}
                        >
                          {att.logs.join('\n')}
                        </Code>
                      </ScrollArea>
                    </Collapsible>
                  )}
                  {att.outputs && Object.keys(att.outputs).length > 0 && (
                    <Collapsible title="Outputs" defaultOpen={false}>
                      <Code block style={{ fontSize: 11 }}>
                        {JSON.stringify(att.outputs, null, 2)}
                      </Code>
                    </Collapsible>
                  )}
                </Paper>
              ))}
            </Stack>
          </Collapsible>
        )}
        {/* ── Unified fullscreen modal with tabs ──────────────────────── */}
        <StageFullscreenModal
          opened={fullscreenOpen}
          onClose={() => setFullscreenOpen(false)}
          initialTabKey={fullscreenTabKey}
          allStages={allStages ?? [stage]}
          currentStage={stage}
          logLines={logLines}
          liveLogsAvailable={liveLogsAvailable}
          logModalScrollRef={logModalScrollRef}
        />
    </Stack>
  );
}
