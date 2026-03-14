import { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router';
import {
  Title,
  Stack,
  Group,
  Button,
  Select,
  Textarea,
  Paper,
  Text,
  Badge,
  Code,
  Loader,
  ScrollArea,
  Divider,
  Timeline,
  ThemeIcon,
  SimpleGrid,
  Card,
  Collapse,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconBug,
  IconPlayerPlay,
  IconCheck,
  IconX,
  IconChevronDown,
  IconChevronUp,
  IconTerminal,
  IconCopy,
} from '@tabler/icons-react';

interface DebugNode {
  name: string;
  description: string;
}

interface DebugResult {
  run_id: string;
  node_name: string;
  sandbox_id: string | null;
  status: string;
  output: Record<string, unknown>;
  logs: string[];
  duration_ms: number;
  error: string;
}

interface Sandbox {
  sandbox_id: string;
  status?: string;
}

interface Repository {
  repo_id: string;
  name: string;
  url: string;
  default_branch: string;
  owner: string;
  provider: string;
}

interface Credential {
  credential_id: string;
  name: string;
  credential_type: string;
  repo_id: string;
}

interface RunDispatch {
  run_id: string;
  node_name: string;
  sandbox_id: string | null;
  stage_id: string;
  status: string;
}

export function Component() {
  const [nodes, setNodes] = useState<DebugNode[]>([]);
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedSandbox, setSelectedSandbox] = useState<string | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [selectedCredential, setSelectedCredential] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [researchContext, setResearchContext] = useState('');
  const [planJson, setPlanJson] = useState('');
  const [previousError, setPreviousError] = useState('');
  const [previousFailedStage, setPreviousFailedStage] = useState('');
  const [continueFromRunId, setContinueFromRunId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DebugResult | null>(null);
  const [history, setHistory] = useState<DebugResult[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [runStatus, setRunStatus] = useState<string>('');
  const logRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch available nodes
  useEffect(() => {
    fetch('/api/v1/debug/nodes')
      .then((r) => r.json())
      .then((data) => {
        const nodeList = (data.nodes as string[]).map((name) => ({
          name,
          description: data.descriptions?.[name] ?? '',
        }));
        setNodes(nodeList);
      })
      .catch(() => {});
  }, []);

  // Fetch sandboxes
  useEffect(() => {
    fetch('/api/v1/sandboxes')
      .then((r) => r.json())
      .then((resp) => {
        const list = (resp.data ?? resp) as Sandbox[];
        setSandboxes(Array.isArray(list) ? list : []);
      })
      .catch(() => {});
  }, []);

  // Fetch repositories
  useEffect(() => {
    fetch('/api/v1/repositories')
      .then((r) => r.json())
      .then((data) => {
        const list = (data.data ?? data) as Repository[];
        setRepositories(Array.isArray(list) ? list : []);
      })
      .catch(() => {});
  }, []);

  // Fetch credentials
  useEffect(() => {
    fetch('/api/v1/credentials')
      .then((r) => r.json())
      .then((data) => {
        const list = (data.data ?? data) as Credential[];
        setCredentials(Array.isArray(list) ? list : []);
      })
      .catch(() => {});
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [liveLogs]);

  // Stream stage logs via SSE
  const streamLogs = useCallback(
    (runId: string, stageId: string, nodeName: string, sandboxId: string | null) => {
      const controller = new AbortController();
      abortRef.current = controller;

      const url = `/api/v1/pipelines/${runId}/stages/${stageId}/logs`;
      fetch(url, { signal: controller.signal })
        .then((resp) => {
          if (!resp.ok || !resp.body) {
            throw new Error(`SSE failed: ${resp.status}`);
          }
          const reader = resp.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          const read = (): void => {
            reader
              .read()
              .then(({ done, value }) => {
                if (done) {
                  setRunning(false);
                  // Fetch final pipeline state for output/duration
                  fetch(`/api/v1/pipelines/${runId}`)
                    .then((r) => r.json())
                    .then((pipeline) => {
                      const pData = pipeline.data ?? pipeline;
                      const stage = pData.stages?.find(
                        (s: { name: string }) => s.name === nodeName
                      );
                      if (stage) {
                        const finalResult: DebugResult = {
                          run_id: runId,
                          node_name: nodeName,
                          sandbox_id: sandboxId,
                          status: stage.status === 'succeeded' ? 'completed' : stage.status,
                          output: stage.outputs ?? {},
                          logs: stage.logs ?? [],
                          duration_ms: stage.duration_ms ?? 0,
                          error: stage.error ?? '',
                        };
                        setResult(finalResult);
                        setLiveLogs(finalResult.logs);
                        setRunStatus(finalResult.status);
                        setHistory((prev) => [finalResult, ...prev].slice(0, 20));
                        if (finalResult.status === 'completed') {
                          notifications.show({
                            title: 'Node completed',
                            message: `${nodeName} finished in ${finalResult.duration_ms}ms`,
                            color: 'green',
                          });
                        } else if (finalResult.error) {
                          notifications.show({
                            title: 'Node failed',
                            message: finalResult.error,
                            color: 'red',
                          });
                        }
                      }
                    })
                    .catch(() => {});
                  return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                  if (!line.startsWith('data: ')) continue;
                  try {
                    const event = JSON.parse(line.slice(6));
                    if (event.type === 'log') {
                      const logLine: string = event.line ?? '';
                      // Detect auth expiry from Claude Code
                      if (logLine.includes('AUTH_EXPIRED:')) {
                        notifications.show({
                          title: 'Authentication expired',
                          message:
                            'OAuth token has expired in the sandbox. Re-authenticate Claude Code in the sandbox to continue.',
                          color: 'red',
                          autoClose: false,
                        });
                        setRunStatus('failed');
                        setRunning(false);
                        controller.abort();
                        return;
                      }
                      setLiveLogs((prev) => [...prev, logLine]);
                    } else if (event.type === 'status') {
                      setRunStatus(event.status);
                    } else if (event.type === 'error') {
                      notifications.show({
                        title: 'Node failed',
                        message: event.message,
                        color: 'red',
                      });
                    }
                  } catch {
                    // ignore parse errors
                  }
                }

                read();
              })
              .catch(() => {
                setRunning(false);
              });
          };

          read();
        })
        .catch(() => {
          setRunning(false);
        });
    },
    []
  );

  // Run node (returns immediately, then streams via SSE)
  const handleRun = async () => {
    if (!selectedNode) return;
    setRunning(true);
    setResult(null);
    setLiveLogs([]);
    setRunStatus('pending');

    // Cancel any previous SSE stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }

    const body: Record<string, unknown> = {
      node_name: selectedNode,
      prompt,
    };
    if (selectedSandbox) body.sandbox_id = selectedSandbox;
    if (researchContext) body.research_context = researchContext;
    if (planJson) {
      try {
        body.plan = JSON.parse(planJson);
      } catch {
        notifications.show({ title: 'Invalid plan JSON', message: 'Could not parse plan', color: 'red' });
        setRunning(false);
        return;
      }
    }
    if (previousError) body.previous_error = previousError;
    if (previousFailedStage) body.previous_failed_stage = previousFailedStage;
    if (continueFromRunId) body.continue_from_run_id = continueFromRunId.trim();
    const repo = repositories.find((r) => r.repo_id === selectedRepo);
    if (repo) body.repo_url = repo.url;
    if (selectedCredential) body.credential_ids = [selectedCredential];

    try {
      const resp = await fetch('/api/v1/debug/run-node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const dispatch = (await resp.json()) as RunDispatch;

      if (!dispatch.run_id || dispatch.status === 'failed') {
        setRunning(false);
        notifications.show({
          title: 'Failed to start',
          message: 'Unknown node or invalid request',
          color: 'red',
        });
        return;
      }

      // Start streaming logs via SSE
      streamLogs(dispatch.run_id, dispatch.stage_id, dispatch.node_name, dispatch.sandbox_id);
    } catch (err) {
      setRunning(false);
      notifications.show({
        title: 'Request failed',
        message: String(err),
        color: 'red',
      });
    }
  };

  const selectedNodeInfo = nodes.find((n) => n.name === selectedNode);
  const needsSandbox = ['research', 'plan', 'implement', 'review', 'setup_workspace'].includes(
    selectedNode ?? ''
  );

  const statusColor =
    runStatus === 'succeeded' || runStatus === 'completed'
      ? 'green'
      : runStatus === 'failed'
        ? 'red'
        : runStatus === 'running'
          ? 'blue'
          : 'gray';

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Group gap="sm">
          <IconBug size={28} />
          <Title order={2}>Debug Console</Title>
        </Group>
        <Badge variant="light" size="lg" color="orange">
          Developer Tool
        </Badge>
      </Group>

      <Text c="dimmed" size="sm">
        Run individual workflow nodes in isolation. Select a node, provide input, and see the output
        with full logs streamed in real-time.
      </Text>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        {/* Left: Controls */}
        <Stack gap="md">
          <Paper withBorder p="md">
            <Stack gap="sm">
              <Select
                label="Workflow Node"
                placeholder="Select a node to run"
                data={nodes.map((n) => ({
                  value: n.name,
                  label: `${n.name} — ${n.description}`,
                }))}
                value={selectedNode}
                onChange={setSelectedNode}
                searchable
              />

              {selectedNodeInfo && (
                <Text size="xs" c="dimmed">
                  {selectedNodeInfo.description}
                </Text>
              )}

              <Textarea
                label="Prompt / Request"
                placeholder="Describe the feature, bug, or task..."
                minRows={3}
                maxRows={8}
                autosize
                value={prompt}
                onChange={(e) => setPrompt(e.currentTarget.value)}
              />

              <Select
                label="Repository"
                placeholder="No repository (empty workspace)"
                data={repositories.map((r) => ({
                  value: r.repo_id,
                  label: `${r.owner}/${r.name}`,
                }))}
                value={selectedRepo}
                onChange={setSelectedRepo}
                searchable
                clearable
              />

              {selectedRepo && credentials.length > 0 && (
                <Select
                  label="Credentials"
                  placeholder="No credentials (public repo)"
                  data={credentials.map((c) => ({
                    value: c.credential_id,
                    label: `${c.name} (${c.credential_type})`,
                  }))}
                  value={selectedCredential}
                  onChange={setSelectedCredential}
                  clearable
                />
              )}

              {needsSandbox && (
                <Select
                  label="Sandbox"
                  placeholder="Auto-pick from pool"
                  data={sandboxes.map((s) => ({
                    value: s.sandbox_id,
                    label: `${s.sandbox_id.slice(0, 12)}...`,
                  }))}
                  value={selectedSandbox}
                  onChange={setSelectedSandbox}
                  clearable
                />
              )}

              <Group justify="space-between">
                <Button
                  variant="subtle"
                  size="xs"
                  rightSection={
                    showAdvanced ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />
                  }
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  Advanced
                </Button>
              </Group>

              <Collapse in={showAdvanced}>
                <Stack gap="sm">
                  <Textarea
                    label="Research Context"
                    placeholder="Paste codebase research context (for plan node)"
                    minRows={3}
                    maxRows={6}
                    autosize
                    value={researchContext}
                    onChange={(e) => setResearchContext(e.currentTarget.value)}
                  />
                  <Textarea
                    label="Plan JSON"
                    placeholder='{"tasks": [...], "summary": "..."}'
                    minRows={3}
                    maxRows={6}
                    autosize
                    value={planJson}
                    onChange={(e) => setPlanJson(e.currentTarget.value)}
                  />
                  <Divider label="Pipeline Continuation" labelPosition="left" />
                  <Textarea
                    label="Previous Error"
                    placeholder="Error message from a previous failed run"
                    minRows={2}
                    maxRows={4}
                    autosize
                    value={previousError}
                    onChange={(e) => setPreviousError(e.currentTarget.value)}
                  />
                  <Select
                    label="Previous Failed Stage"
                    placeholder="Stage that failed"
                    data={nodes.map((n) => ({ value: n.name, label: n.name }))}
                    value={previousFailedStage || null}
                    onChange={(v) => setPreviousFailedStage(v ?? '')}
                    clearable
                  />
                  <Group gap="xs" align="end">
                    <Textarea
                      label="Continue from Run ID"
                      placeholder="Paste a run ID to auto-load its outputs"
                      minRows={1}
                      maxRows={1}
                      value={continueFromRunId}
                      onChange={(e) => setContinueFromRunId(e.currentTarget.value)}
                      style={{ flex: 1 }}
                    />
                    <Tooltip label="Load outputs from this run into the fields above">
                      <Button
                        variant="light"
                        size="xs"
                        disabled={!continueFromRunId}
                        onClick={async () => {
                          try {
                            const resp = await fetch(
                              `/api/v1/pipelines/${continueFromRunId.trim()}`
                            );
                            if (!resp.ok) {
                              notifications.show({
                                title: 'Pipeline not found',
                                message: `GET /pipelines/${continueFromRunId.trim()} returned ${resp.status}`,
                                color: 'red',
                              });
                              return;
                            }
                            const data = await resp.json();
                            const pipeline = data.data ?? data;
                            for (const stage of pipeline.stages ?? []) {
                              const outputs = stage.outputs ?? {};
                              if (stage.status === 'succeeded') {
                                if (stage.name === 'research' && outputs.research_report) {
                                  setResearchContext(outputs.research_report);
                                } else if (stage.name === 'plan' && outputs.plan) {
                                  setPlanJson(
                                    typeof outputs.plan === 'string'
                                      ? outputs.plan
                                      : JSON.stringify(outputs.plan, null, 2)
                                  );
                                }
                              } else if (stage.status === 'failed' && stage.error) {
                                setPreviousError(stage.error);
                                setPreviousFailedStage(stage.name);
                              }
                            }
                            notifications.show({
                              title: 'Loaded',
                              message: `Loaded outputs from ${continueFromRunId.slice(0, 12)}`,
                              color: 'green',
                            });
                          } catch {
                            notifications.show({
                              title: 'Failed to load',
                              message: 'Could not fetch pipeline run',
                              color: 'red',
                            });
                          }
                        }}
                      >
                        Load
                      </Button>
                    </Tooltip>
                  </Group>
                </Stack>
              </Collapse>

              <Button
                leftSection={
                  running ? <Loader size={16} color="white" /> : <IconPlayerPlay size={16} />
                }
                onClick={handleRun}
                disabled={!selectedNode}
                fullWidth
                size="md"
              >
                {running ? 'Running...' : 'Run Node'}
              </Button>
            </Stack>
          </Paper>

          {/* Node quick-select grid */}
          <SimpleGrid cols={3} spacing="xs">
            {nodes.map((node) => (
              <Card
                key={node.name}
                withBorder
                padding="xs"
                style={{
                  cursor: 'pointer',
                  borderColor:
                    selectedNode === node.name ? 'var(--mantine-color-blue-5)' : undefined,
                  backgroundColor:
                    selectedNode === node.name ? 'var(--mantine-color-blue-light)' : undefined,
                }}
                onClick={() => setSelectedNode(node.name)}
              >
                <Text size="xs" fw={600} truncate>
                  {node.name}
                </Text>
              </Card>
            ))}
          </SimpleGrid>
        </Stack>

        {/* Right: Results */}
        <Stack gap="md">
          {/* Live logs / result logs */}
          <Paper withBorder p="md">
            <Group justify="space-between" mb="xs">
              <Group gap="xs">
                <IconTerminal size={16} />
                <Text size="sm" fw={600}>
                  Logs
                </Text>
              </Group>
              <Group gap="xs">
                {(running || runStatus) && (
                  <Badge color={statusColor} variant="light">
                    {running ? runStatus || 'starting' : result?.status ?? runStatus}
                  </Badge>
                )}
                {result && (
                  <Badge variant="outline" size="sm">
                    {result.duration_ms}ms
                  </Badge>
                )}
              </Group>
            </Group>
            <ScrollArea h={300} viewportRef={logRef}>
              {running && liveLogs.length === 0 && (
                <Group gap="xs" p="md" justify="center">
                  <Loader size="sm" />
                  <Text size="sm" c="dimmed">
                    Waiting for output...
                  </Text>
                </Group>
              )}
              {liveLogs.length > 0 && (
                <Code block style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
                  {liveLogs.map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))}
                </Code>
              )}
              {!running && liveLogs.length === 0 && !result && (
                <Text size="sm" c="dimmed" ta="center" p="xl">
                  Run a node to see logs here
                </Text>
              )}
            </ScrollArea>
          </Paper>

          {/* Output */}
          {result && (
            <Paper withBorder p="md">
              <Group justify="space-between" mb="xs">
                <Text size="sm" fw={600}>
                  Output
                </Text>
                <Tooltip label="Copy output">
                  <ActionIcon
                    variant="subtle"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(result.output, null, 2));
                      notifications.show({
                        message: 'Copied to clipboard',
                        color: 'green',
                      });
                    }}
                  >
                    <IconCopy size={14} />
                  </ActionIcon>
                </Tooltip>
              </Group>
              <ScrollArea h={250}>
                <Code block style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
                  {JSON.stringify(result.output, null, 2)}
                </Code>
              </ScrollArea>
              {result.error && (
                <>
                  <Divider my="xs" />
                  <Text size="sm" c="red" fw={500}>
                    Error: {result.error}
                  </Text>
                </>
              )}
              <Divider my="xs" />
              <Group gap="xs">
                <Text
                  size="xs"
                  c="dimmed"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    navigator.clipboard.writeText(result.run_id);
                    notifications.show({ message: 'Run ID copied', color: 'green' });
                  }}
                >
                  Run ID: {result.run_id}
                </Text>
                {result.sandbox_id && (
                  <Text size="xs" c="dimmed">
                    | Sandbox: {result.sandbox_id.slice(0, 12)}
                  </Text>
                )}
              </Group>
            </Paper>
          )}
        </Stack>
      </SimpleGrid>

      {/* History */}
      {history.length > 0 && (
        <>
          <Divider label="Run History" labelPosition="center" />
          <Timeline active={0} bulletSize={24}>
            {history.map((h) => (
              <Timeline.Item
                key={h.run_id}
                bullet={
                  <ThemeIcon
                    size={24}
                    radius="xl"
                    color={h.status === 'completed' ? 'green' : 'red'}
                    variant="filled"
                  >
                    {h.status === 'completed' ? (
                      <IconCheck size={12} />
                    ) : (
                      <IconX size={12} />
                    )}
                  </ThemeIcon>
                }
                title={
                  <Group gap="xs">
                    <Text size="sm" fw={500}>
                      {h.node_name}
                    </Text>
                    <Badge size="xs" variant="outline">
                      {h.duration_ms}ms
                    </Badge>
                  </Group>
                }
              >
                <Text size="xs" c="dimmed">
                  {h.run_id.slice(0, 12)} | {h.logs.length} log lines
                  {h.error ? ` | ${h.error.slice(0, 60)}` : ''}
                </Text>
                <Button
                  variant="subtle"
                  size="xs"
                  mt={4}
                  onClick={() => {
                    setResult(h);
                    setLiveLogs(h.logs);
                    setRunStatus(h.status);
                  }}
                >
                  View
                </Button>
              </Timeline.Item>
            ))}
          </Timeline>
        </>
      )}
    </Stack>
  );
}

Component.displayName = 'DebugPage';
