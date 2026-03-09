import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center, Tabs,
  Code, ScrollArea,
} from '@mantine/core';
import { IconArrowLeft, IconCheck, IconRefresh, IconX } from '@tabler/icons-react';
import { StageReportEditor } from '../components/StageReportEditor';
import { PlanView } from '../components/PlanView';
import {
  usePipelinesGetPipeline,
  usePipelinesListStages,
} from '@/generated/api/pipelines/pipelines';
import { PipelineDAG } from '../components/PipelineDAG';
import { DiffView } from '@/shared/components/DiffView';
import { StepTimingBar } from '../components/StepTimingBar';
import { usePipelineSSE } from '../hooks/usePipelineSSE';
import { TimeAgo } from '@/shared/components/TimeAgo';

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

interface StageItem {
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

function useStageLogs(runId: string | undefined, stageId: string | null, stageStatus: string | undefined) {
  const [lines, setLines] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId || !stageId) {
      setLines([]);
      return;
    }

    // Only use SSE for running stages
    if (stageStatus !== 'running') {
      setLines([]);
      return;
    }

    const es = new EventSource(`/api/v1/pipelines/${runId}/stages/${stageId}/logs`);

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

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId, stageId, stageStatus]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines]);

  return { lines, scrollRef };
}

export function Component() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  const { data: pipelineResp, isLoading, refetch: refetchPipeline } = usePipelinesGetPipeline(runId ?? '', {
    query: { staleTime: 0 },
  });
  const { data: stagesResp, refetch: refetchStages } = usePipelinesListStages(runId ?? '', {
    query: { enabled: !!runId, staleTime: 0 },
  });

  // Real-time updates via SSE — refetch data on every stage/pipeline change
  const sse = usePipelineSSE(runId ?? null);
  useEffect(() => {
    sse.onUpdate(() => {
      refetchPipeline();
      refetchStages();
    });
  }, [sse.onUpdate, refetchPipeline, refetchStages]);

  const pipeline = (pipelineResp?.data ?? {}) as Record<string, unknown>;
  const stages = (stagesResp?.data ?? []) as StageItem[];
  const selectedStage = selectedStageId ? stages.find((s) => s.stage_id === selectedStageId) : null;

  const { lines: logLines, scrollRef: logScrollRef } = useStageLogs(runId, selectedStageId, selectedStage?.status);

  const handleRetry = useCallback(async () => {
    if (!runId || !selectedStageId) return;
    setRetrying(true);
    try {
      await fetch(`/api/v1/pipelines/${runId}/stages/${selectedStageId}/retry`, { method: 'POST' });
    } finally {
      setRetrying(false);
    }
  }, [runId, selectedStageId]);

  const handleApprove = useCallback(async () => {
    if (!runId || !selectedStageId) return;
    setApproving(true);
    try {
      await fetch(`/api/v1/pipelines/${runId}/stages/${selectedStageId}/approve`, { method: 'POST' });
    } finally {
      setApproving(false);
    }
  }, [runId, selectedStageId]);

  const handleReject = useCallback(async () => {
    if (!runId || !selectedStageId) return;
    setRejecting(true);
    try {
      await fetch(`/api/v1/pipelines/${runId}/stages/${selectedStageId}/reject`, { method: 'POST' });
    } finally {
      setRejecting(false);
    }
  }, [runId, selectedStageId]);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const mapStageType = (stageType: string | undefined): string => {
    if (!stageType) return 'agentStep';
    if (stageType.includes('approve') || stageType.includes('approval')) return 'approvalGate';
    return 'agentStep';
  };

  const dagNodes = stages.map((s) => ({
    id: s.stage_id,
    type: mapStageType(s.stage_type),
    label: s.name,
    status: s.status,
  }));

  const dagEdges = stages.slice(1).map((s, i) => ({
    source: stages[i]!.stage_id,
    target: s.stage_id,
  }));

  const timingSteps = stages
    .filter((s) => s.started_at && s.finished_at)
    .map((s) => ({
      name: s.name,
      stepType: s.stage_type ?? 'agent',
      durationMs: s.duration_ms ?? 0,
      startMs: s.started_at ? new Date(s.started_at).getTime() : 0,
    }));

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="sm">
          <Button
            variant="subtle"
            size="compact-sm"
            leftSection={<IconArrowLeft size={14} />}
            onClick={() => navigate('/pipelines')}
          >
            Back
          </Button>
          <Title order={2}>Pipeline {runId?.slice(0, 8)}</Title>
          <Badge color={statusColor[pipeline.status as string] ?? 'gray'}>
            {pipeline.status as string ?? 'unknown'}
          </Badge>
        </Group>
        <Group gap="sm">
          {(pipeline.trigger_type as string)?.startsWith('chat:') && (
            <Button
              variant="light"
              size="compact-sm"
              onClick={() => navigate(`/chat/${(pipeline.trigger_type as string).slice(5)}`)}
            >
              View Chat
            </Button>
          )}
          <Button
            variant="light"
            size="compact-sm"
            onClick={() => navigate(`/pipelines/runs/${runId}`)}
          >
            Event Log
          </Button>
        </Group>
      </Group>

      <Tabs defaultValue="dag">
        <Tabs.List>
          <Tabs.Tab value="dag">Pipeline DAG</Tabs.Tab>
          <Tabs.Tab value="timing">Step Timing</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="dag" pt="md">
          {dagNodes.length > 0 ? (
            <>
              <PipelineDAG
                nodes={dagNodes}
                edges={dagEdges}
                onNodeClick={(nodeId) => setSelectedStageId(nodeId === selectedStageId ? null : nodeId)}
              />
              {selectedStage && (
                <Paper withBorder p="md" mt="md">
                  <Stack gap="sm">
                    <Group justify="space-between">
                      <Group gap="xs">
                        <Text fw={600}>{selectedStage.name}</Text>
                        <Badge color={statusColor[selectedStage.status] ?? 'gray'}>{selectedStage.status}</Badge>
                      </Group>
                      <Group gap="xs">
                        {selectedStage.status === 'waiting_approval' && (
                          <Button
                            variant="filled"
                            color="green"
                            size="compact-sm"
                            leftSection={<IconCheck size={14} />}
                            loading={approving}
                            onClick={handleApprove}
                          >
                            Approve
                          </Button>
                        )}
                        {selectedStage.status === 'waiting_approval' && (
                          <Button
                            variant="light"
                            color="red"
                            size="compact-sm"
                            leftSection={<IconX size={14} />}
                            loading={rejecting}
                            onClick={handleReject}
                          >
                            Reject
                          </Button>
                        )}
                        {(selectedStage.status === 'failed' || selectedStage.status === 'running') && (
                          <Button
                            variant="light"
                            size="compact-sm"
                            leftSection={<IconRefresh size={14} />}
                            loading={retrying}
                            disabled={(selectedStage.retry_count ?? 0) >= 3}
                            onClick={handleRetry}
                          >
                            {selectedStage.status === 'failed' ? 'Retry' : 'Restart'}
                            {(selectedStage.retry_count ?? 0) > 0 && ` (${selectedStage.retry_count}/3)`}
                          </Button>
                        )}
                      </Group>
                    </Group>
                    <Text size="sm" c="dimmed">Type: {selectedStage.stage_type ?? '—'}</Text>
                    <Group gap={4}><Text size="sm">Started:</Text><TimeAgo date={selectedStage.started_at} size="sm" /></Group>
                    <Group gap={4}><Text size="sm">Finished:</Text><TimeAgo date={selectedStage.finished_at} size="sm" /></Group>
                    {selectedStage.duration_ms ? (
                      <Text size="sm">Duration: {(selectedStage.duration_ms / 1000).toFixed(1)}s</Text>
                    ) : null}

                    {/* Sandbox info */}
                    {!!selectedStage.outputs?.sandbox_id && (
                      <Group gap="xs">
                        <Text size="sm">Sandbox:</Text>
                        <Badge
                          variant="light"
                          size="lg"
                          radius="sm"
                          style={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/sandboxes/${selectedStage.outputs!.sandbox_id}`)}
                        >
                          {(selectedStage.outputs.sandbox_id as string).slice(0, 12)}
                        </Badge>
                      </Group>
                    )}

                    {/* Error */}
                    {selectedStage.error && (
                      <Paper withBorder p="sm" style={{ borderColor: 'var(--mantine-color-red-6)' }}>
                        <Text size="sm" fw={600} c="red" mb={4}>Error</Text>
                        <Text size="sm" c="red" style={{ whiteSpace: 'pre-wrap' }}>{selectedStage.error}</Text>
                      </Paper>
                    )}

                    {/* Live logs for running stages */}
                    {selectedStage.status === 'running' && logLines.length > 0 && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Logs</Text>
                        <ScrollArea
                          h={200}
                          viewportRef={logScrollRef}
                          style={{ backgroundColor: 'var(--mantine-color-dark-8)', borderRadius: 4 }}
                        >
                          <Code
                            block
                            style={{
                              backgroundColor: 'transparent',
                              whiteSpace: 'pre',
                              fontSize: 12,
                            }}
                          >
                            {logLines.join('\n')}
                          </Code>
                        </ScrollArea>
                      </Stack>
                    )}

                    {/* Completed stage logs from data */}
                    {selectedStage.status !== 'running' && selectedStage.logs && selectedStage.logs.length > 0 && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Logs</Text>
                        <ScrollArea
                          h={200}
                          style={{ backgroundColor: 'var(--mantine-color-dark-8)', borderRadius: 4 }}
                        >
                          <Code
                            block
                            style={{
                              backgroundColor: 'transparent',
                              whiteSpace: 'pre',
                              fontSize: 12,
                            }}
                          >
                            {selectedStage.logs.join('\n')}
                          </Code>
                        </ScrollArea>
                      </Stack>
                    )}

                    {/* Research report — editable */}
                    {!!selectedStage.outputs?.research_report && (
                      <StageReportEditor
                        runId={runId!}
                        stageId={selectedStage.stage_id}
                        stageName={selectedStage.name}
                        initialContent={selectedStage.outputs.research_report as string}
                        status={selectedStage.status}
                      />
                    )}

                    {/* Plan output — structured view */}
                    {!!selectedStage.outputs?.plan && (
                      <PlanView plan={selectedStage.outputs.plan as unknown as React.ComponentProps<typeof PlanView>['plan']} />
                    )}

                    {/* Diff output — code changes view */}
                    {!!selectedStage.outputs?.diff && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Code Changes</Text>
                        <DiffView content={selectedStage.outputs.diff as string} />
                      </Stack>
                    )}

                    {/* Other outputs (non-plan, non-diff, non-research) */}
                    {selectedStage.outputs && Object.keys(selectedStage.outputs).filter(k => !['plan', 'research_report', 'diff'].includes(k)).length > 0 && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Outputs</Text>
                        <Code block style={{ fontSize: 12 }}>
                          {JSON.stringify(
                            Object.fromEntries(Object.entries(selectedStage.outputs).filter(([k]) => !['plan', 'research_report', 'diff'].includes(k))),
                            null, 2,
                          )}
                        </Code>
                      </Stack>
                    )}
                  </Stack>
                </Paper>
              )}
            </>
          ) : (
            <Paper withBorder p="md">
              <Text c="dimmed">No stages to visualize</Text>
            </Paper>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="timing" pt="md">
          {timingSteps.length > 0 ? (
            <StepTimingBar steps={timingSteps} />
          ) : (
            <Paper withBorder p="md">
              <Text c="dimmed">No timing data available</Text>
            </Paper>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
