import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center, Tabs,
  Code, ScrollArea,
} from '@mantine/core';
import { IconArrowLeft, IconCheck, IconRefresh, IconX } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../../chat/chat-markdown.css';
import {
  usePipelinesGetPipeline,
  usePipelinesListStages,
} from '@/generated/api/pipelines/pipelines';
import { PipelineDAG } from '../components/PipelineDAG';
import { StepTimingBar } from '../components/StepTimingBar';

const statusColor: Record<string, string> = {
  pending: 'gray',
  running: 'blue',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'orange',
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

  const { data: pipelineResp, isLoading } = usePipelinesGetPipeline(runId ?? '', {
    query: { refetchInterval: 3000 },
  });
  const { data: stagesResp } = usePipelinesListStages(runId ?? '', {
    query: { enabled: !!runId, refetchInterval: 3000 },
  });

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
    source: stages[i].stage_id,
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
                    <Text size="sm">Started: {selectedStage.started_at ? new Date(selectedStage.started_at).toLocaleString() : '—'}</Text>
                    <Text size="sm">Finished: {selectedStage.finished_at ? new Date(selectedStage.finished_at).toLocaleString() : '—'}</Text>
                    {selectedStage.duration_ms ? (
                      <Text size="sm">Duration: {(selectedStage.duration_ms / 1000).toFixed(1)}s</Text>
                    ) : null}

                    {/* Sandbox info */}
                    {selectedStage.outputs?.sandbox_id && (
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

                    {/* Research report — rendered as markdown */}
                    {selectedStage.outputs?.research_report && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Research Report</Text>
                        <Paper withBorder p="sm">
                          <ScrollArea.Autosize mah={500}>
                            <div className="chat-markdown" style={{ fontSize: 13 }}>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {selectedStage.outputs.research_report as string}
                              </ReactMarkdown>
                            </div>
                          </ScrollArea.Autosize>
                        </Paper>
                      </Stack>
                    )}

                    {/* Plan output — rendered as task list */}
                    {selectedStage.outputs?.plan && (
                      <Stack gap="sm">
                        <Text size="sm" fw={600}>Plan</Text>
                        {(selectedStage.outputs.plan as { summary?: string })?.summary && (
                          <Text size="sm" c="dimmed" mb={4}>
                            {(selectedStage.outputs.plan as { summary: string }).summary}
                          </Text>
                        )}
                        <Stack gap="xs">
                          {((selectedStage.outputs.plan as { tasks?: Array<{ title?: string; description?: string; complexity?: string; file_paths?: string[] }> })?.tasks ?? []).map(
                            (task, i) => (
                              <Paper key={i} withBorder p="sm" radius="sm">
                                <Stack gap="xs">
                                  <Group justify="space-between" align="center">
                                    <Group gap="xs">
                                      <Badge size="lg" circle variant="light" color="blue">{i + 1}</Badge>
                                      <Text size="sm" fw={600}>{task.title ?? 'Task'}</Text>
                                    </Group>
                                    {task.complexity && (
                                      <Badge
                                        size="sm"
                                        variant="light"
                                        color={
                                          task.complexity === 'XL' ? 'red' :
                                          task.complexity === 'L' ? 'orange' :
                                          task.complexity === 'M' ? 'yellow' :
                                          'green'
                                        }
                                      >
                                        {task.complexity}
                                      </Badge>
                                    )}
                                  </Group>
                                  {task.file_paths && task.file_paths.length > 0 && (
                                    <Group gap={4}>
                                      {task.file_paths.map((fp, j) => (
                                        <Badge key={j} size="xs" variant="dot" color="gray" radius="sm">
                                          {fp}
                                        </Badge>
                                      ))}
                                    </Group>
                                  )}
                                  {task.description && (
                                    <ScrollArea.Autosize mah={300}>
                                      <div className="chat-markdown" style={{ fontSize: 12 }}>
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                          {task.description}
                                        </ReactMarkdown>
                                      </div>
                                    </ScrollArea.Autosize>
                                  )}
                                </Stack>
                              </Paper>
                            ),
                          )}
                        </Stack>
                      </Stack>
                    )}

                    {/* Other outputs (non-plan) */}
                    {selectedStage.outputs && Object.keys(selectedStage.outputs).filter(k => k !== 'plan' && k !== 'research_report').length > 0 && (
                      <Stack gap={4}>
                        <Text size="sm" fw={600}>Outputs</Text>
                        <Code block style={{ fontSize: 12 }}>
                          {JSON.stringify(
                            Object.fromEntries(Object.entries(selectedStage.outputs).filter(([k]) => k !== 'plan' && k !== 'research_report')),
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
