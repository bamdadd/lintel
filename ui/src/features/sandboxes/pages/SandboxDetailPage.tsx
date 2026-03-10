import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Group, Badge, Text, Button, Paper, Loader, Center,
  Code, TextInput, ScrollArea, ActionIcon, Tabs, UnstyledButton,
} from '@mantine/core';
import {
  IconArrowLeft, IconRefresh, IconTrash, IconEraser,
  IconFolder, IconFolderOpen, IconFile, IconChevronRight, IconChevronDown,
} from '@tabler/icons-react';
import {
  useSandboxesGetSandboxStatus,
  useSandboxesExecuteCommand,
  useSandboxesDestroySandbox,
} from '@/generated/api/sandboxes/sandboxes';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';

interface MountEntry {
  source: string;
  target: string;
  type: string;
}

interface SandboxMetadata {
  sandbox_id: string;
  image: string;
  network_enabled: boolean;
  workspace_id: string;
  channel_id: string;
  devcontainer?: Record<string, unknown>;
  mounts?: MountEntry[];
}

function useSandboxMetadata(sandboxId: string | undefined) {
  return useQuery<SandboxMetadata | null>({
    queryKey: ['/api/v1/sandboxes', sandboxId],
    queryFn: async () => {
      const res = await fetch('/api/v1/sandboxes');
      const list: SandboxMetadata[] = await res.json();
      return list.find((s) => s.sandbox_id === sandboxId) ?? null;
    },
    enabled: !!sandboxId,
  });
}

function useSandboxLogs(sandboxId: string | undefined, enabled: boolean) {
  return useQuery<string>({
    queryKey: ['/api/v1/sandboxes', sandboxId, 'logs'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/sandboxes/${sandboxId}/logs?tail=500`);
      if (!res.ok) return '';
      const data = await res.json();
      return data.logs ?? '';
    },
    enabled: !!sandboxId && enabled,
    refetchInterval: 3000,
  });
}

interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileNode[];
}

function useFileTree(sandboxId: string | undefined, enabled: boolean) {
  return useQuery<FileNode[]>({
    queryKey: ['/api/v1/sandboxes', sandboxId, 'tree'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/sandboxes/${sandboxId}/tree?path=/workspace&depth=4`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.children ?? [];
    },
    enabled: !!sandboxId && enabled,
  });
}

function FileTreeNode({
  node, depth, selectedPath, onSelect,
}: {
  node: FileNode; depth: number; selectedPath: string | null;
  onSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(depth < 1);
  const isDir = node.type === 'directory';
  const isSelected = node.path === selectedPath;

  return (
    <>
      <UnstyledButton
        onClick={() => { if (isDir) setOpen(!open); onSelect(node.path); }}
        py={2}
        px={4}
        style={{
          display: 'flex', alignItems: 'center', gap: 4,
          paddingLeft: depth * 16 + 4,
          borderRadius: 4,
          backgroundColor: isSelected ? 'var(--mantine-color-dark-5)' : undefined,
          width: '100%',
        }}
      >
        {isDir ? (
          open ? <IconChevronDown size={12} /> : <IconChevronRight size={12} />
        ) : (
          <span style={{ width: 12 }} />
        )}
        {isDir ? (
          open ? <IconFolderOpen size={14} color="var(--mantine-color-blue-4)" />
            : <IconFolder size={14} color="var(--mantine-color-blue-4)" />
        ) : (
          <IconFile size={14} color="var(--mantine-color-gray-5)" />
        )}
        <Text size="xs" ff="monospace" truncate style={{ flex: 1 }}>{node.name}</Text>
        {!isDir && node.size !== undefined && (
          <Text size="xs" c="dimmed" ff="monospace">
            {node.size > 1024 ? `${(node.size / 1024).toFixed(1)}K` : `${node.size}B`}
          </Text>
        )}
      </UnstyledButton>
      {isDir && open && node.children?.map((child) => (
        <FileTreeNode
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

interface TerminalLine {
  type: 'input' | 'output' | 'error';
  text: string;
}

export function Component() {
  const { sandboxId } = useParams<{ sandboxId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: statusResp } = useSandboxesGetSandboxStatus(sandboxId ?? '', {
    query: { enabled: !!sandboxId, refetchInterval: 5000 },
  });
  const { data: metadata, isLoading: metaLoading } = useSandboxMetadata(sandboxId);
  const executeMutation = useSandboxesExecuteCommand();
  const destroyMutation = useSandboxesDestroySandbox();
  const [cleaningUp, setCleaningUp] = useState(false);

  const [activeTab, setActiveTab] = useState<string | null>('files');
  const [command, setCommand] = useState('');
  const [cwd, setCwd] = useState('/workspace');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [running, setRunning] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const logScrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: containerLogs } = useSandboxLogs(sandboxId, activeTab === 'logs');
  const { data: fileTree, isLoading: treeLoading } = useFileTree(sandboxId, activeTab === 'files');

  const handleFileSelect = useCallback(async (path: string) => {
    setSelectedFile(path);
    // Try to read the file content
    if (!sandboxId) return;
    setFileLoading(true);
    try {
      const res = await fetch(`/api/v1/sandboxes/${sandboxId}/files?path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content ?? null);
      } else {
        setFileContent(null);
      }
    } catch {
      setFileContent(null);
    } finally {
      setFileLoading(false);
    }
  }, [sandboxId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lines]);

  useEffect(() => {
    if (!running) {
      inputRef.current?.focus();
    }
  }, [running]);

  const status = (statusResp?.data as { status?: string } | undefined)?.status ?? 'unknown';

  const statusColor: Record<string, string> = {
    running: 'green',
    stopped: 'gray',
    unknown: 'yellow',
    error: 'red',
  };

  const prompt = `root ➜ ${cwd} $`;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (history.length === 0) return;
      const newIndex = historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex;
      setHistoryIndex(newIndex);
      setCommand(history[history.length - 1 - newIndex] ?? '');
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex <= 0) {
        setHistoryIndex(-1);
        setCommand('');
      } else {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCommand(history[history.length - 1 - newIndex] ?? '');
      }
    } else if (e.key === 'Enter') {
      handleExecute();
    }
  };

  const handleExecute = () => {
    if (!command.trim() || !sandboxId) return;
    const cmd = command.trim();
    setHistory((prev) => [...prev, cmd]);
    setHistoryIndex(-1);
    setCommand('');
    setLines((prev) => [...prev, { type: 'input', text: `${prompt} ${cmd}` }]);
    setRunning(true);

    // Wrap cd commands so we can track the working directory
    const isCd = /^cd\s+/.test(cmd) || cmd === 'cd';
    const execCmd = isCd
      ? `${cmd} && pwd`
      : cmd;

    executeMutation.mutate(
      { sandboxId, data: { command: execCmd, timeout_seconds: 30, workdir: cwd } },
      {
        onSuccess: (resp) => {
          const data = resp.data as { stdout?: string; stderr?: string; exit_code?: number };
          if (isCd && data.exit_code === 0 && data.stdout?.trim()) {
            setCwd(data.stdout.trim().split('\n').pop() ?? cwd);
          }
          const output = isCd ? '' : (data.stdout ?? '');
          if (output) {
            setLines((prev) => [...prev, { type: 'output', text: output }]);
          }
          if (data.stderr) {
            setLines((prev) => [...prev, { type: 'error', text: data.stderr! }]);
          }
          if (!output && !data.stderr && !isCd) {
            setLines((prev) => [...prev, { type: 'output', text: '(no output)' }]);
          }
          if (data.exit_code !== undefined && data.exit_code !== 0) {
            setLines((prev) => [...prev, { type: 'error', text: `exit code: ${data.exit_code}` }]);
          }
          setRunning(false);
          inputRef.current?.focus();
        },
        onError: (err) => {
          setLines((prev) => [...prev, { type: 'error', text: String(err) }]);
          setRunning(false);
          inputRef.current?.focus();
        },
      },
    );
  };

  const handleCleanupWorkspace = async () => {
    if (!sandboxId) return;
    setCleaningUp(true);
    try {
      const res = await fetch(`/api/v1/sandboxes/${sandboxId}/cleanup-workspace`, {
        method: 'POST',
      });
      if (res.ok) {
        notifications.show({ title: 'Workspace cleaned', message: 'All files in /workspace removed', color: 'teal' });
        void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes', sandboxId, 'tree'] });
      } else {
        const data = await res.json().catch(() => ({ detail: 'Unknown error' }));
        notifications.show({ title: 'Cleanup failed', message: data.detail ?? 'Unknown error', color: 'red' });
      }
    } catch (err) {
      notifications.show({ title: 'Cleanup failed', message: String(err), color: 'red' });
    } finally {
      setCleaningUp(false);
    }
  };

  const handleDestroy = () => {
    if (!sandboxId) return;
    destroyMutation.mutate(
      { sandboxId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Destroyed', message: 'Sandbox removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes'] });
          navigate('/sandboxes');
        },
      },
    );
  };

  if (metaLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group>
        <ActionIcon variant="subtle" onClick={() => navigate('/sandboxes')}>
          <IconArrowLeft size={20} />
        </ActionIcon>
        <Title order={2}>Sandbox {sandboxId?.slice(0, 12)}</Title>
        <Badge color={statusColor[status] ?? 'gray'} size="lg">{status}</Badge>
      </Group>

      <Group gap="xl">
        <Text size="sm"><Text span fw={600}>ID:</Text> <Code>{sandboxId}</Code></Text>
        {metadata && (
          <>
            <Text size="sm"><Text span fw={600}>Image:</Text> {metadata.devcontainer?.image as string ?? metadata.image}</Text>
            <Group gap={4} align="center"><Text size="sm" fw={600}>Network:</Text><Badge size="xs" color={metadata.network_enabled ? 'green' : 'gray'}>{metadata.network_enabled ? 'on' : 'off'}</Badge></Group>
          </>
        )}
      </Group>

      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List>
          <Tabs.Tab value="files">Files</Tabs.Tab>
          <Tabs.Tab value="terminal">Terminal</Tabs.Tab>
          <Tabs.Tab value="logs">Container Logs</Tabs.Tab>
          <Tabs.Tab value="config">Configuration</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="files" pt="md">
          <Group align="flex-start" gap="md" wrap="nowrap">
            <Paper withBorder p="xs" radius="md" style={{ minWidth: 280, maxWidth: 350, minHeight: 450 }}>
              <Group justify="space-between" mb="xs">
                <Text size="xs" fw={600} c="dimmed">/workspace</Text>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={() => queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes', sandboxId, 'tree'] })}
                >
                  <IconRefresh size={14} />
                </ActionIcon>
              </Group>
              <ScrollArea h={420}>
                {treeLoading ? (
                  <Center py="xl"><Loader size="sm" /></Center>
                ) : fileTree && fileTree.length > 0 ? (
                  fileTree.map((node) => (
                    <FileTreeNode
                      key={node.path}
                      node={node}
                      depth={0}
                      selectedPath={selectedFile}
                      onSelect={handleFileSelect}
                    />
                  ))
                ) : (
                  <Text size="xs" c="dimmed" ta="center" py="xl">No files found</Text>
                )}
              </ScrollArea>
            </Paper>
            <Paper withBorder p="xs" radius="md" bg="dark.9" style={{ flex: 1, minHeight: 450 }}>
              {selectedFile ? (
                <>
                  <Group justify="space-between" mb="xs">
                    <Text size="xs" ff="monospace" c="dimmed" truncate>{selectedFile}</Text>
                  </Group>
                  <ScrollArea h={420}>
                    {fileLoading ? (
                      <Center py="xl"><Loader size="sm" /></Center>
                    ) : fileContent !== null ? (
                      <Code block style={{ fontSize: 12, background: 'transparent', whiteSpace: 'pre' }}>
                        {fileContent}
                      </Code>
                    ) : (
                      <Text size="xs" c="dimmed" ta="center" py="xl">
                        Cannot preview this file (binary or directory)
                      </Text>
                    )}
                  </ScrollArea>
                </>
              ) : (
                <Center h={450}>
                  <Text size="sm" c="dimmed">Select a file to view its contents</Text>
                </Center>
              )}
            </Paper>
          </Group>
        </Tabs.Panel>

        <Tabs.Panel value="terminal" pt="md">
          <Paper withBorder p="xs" radius="md" bg="dark.9" style={{ minHeight: 400 }}>
            <ScrollArea h={350} viewportRef={scrollRef}>
              <Code block style={{ fontSize: 12, background: 'transparent', whiteSpace: 'pre-wrap' }}>
                {lines.length === 0 && (
                  <Text size="xs" c="dimmed">Run commands in the sandbox. Try: ls /workspace</Text>
                )}
                {lines.map((line, i) => {
                  if (line.type === 'input') {
                    // Split prompt from command for coloring
                    const dollarIdx = line.text.indexOf('$ ');
                    const promptPart = dollarIdx >= 0 ? line.text.slice(0, dollarIdx + 1) : '';
                    const cmdPart = dollarIdx >= 0 ? line.text.slice(dollarIdx + 2) : line.text;
                    return (
                      <Text key={i} size="xs" ff="monospace" style={{ whiteSpace: 'pre-wrap' }}>
                        <Text span c="green.4">{promptPart}</Text>{' '}
                        <Text span c="gray.1">{cmdPart}</Text>
                      </Text>
                    );
                  }
                  return (
                    <Text
                      key={i}
                      size="xs"
                      ff="monospace"
                      c={line.type === 'error' ? 'red.4' : 'gray.3'}
                      style={{ whiteSpace: 'pre-wrap' }}
                    >
                      {line.text}
                    </Text>
                  );
                })}
              </Code>
            </ScrollArea>
            <Group mt="xs" gap={4} align="center">
              <Text size="xs" ff="monospace" c="green.4" style={{ whiteSpace: 'nowrap', userSelect: 'none' }}>
                {prompt}
              </Text>
              <TextInput
                ref={inputRef}
                flex={1}
                variant="unstyled"
                value={command}
                onChange={(e) => setCommand(e.currentTarget.value)}
                onKeyDown={handleKeyDown}
                disabled={running}
                autoFocus
                styles={{ input: { fontFamily: 'monospace', fontSize: 12, color: 'var(--mantine-color-gray-3)', padding: 0 } }}
              />
            </Group>
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="logs" pt="md">
          <Paper withBorder p="xs" radius="md" bg="dark.9" style={{ minHeight: 400 }}>
            <Group justify="space-between" mb="xs">
              <Text size="xs" c="dimmed">Docker container logs (last 500 lines, auto-refreshing)</Text>
              <ActionIcon
                variant="subtle"
                size="sm"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['/api/v1/sandboxes', sandboxId, 'logs'] })}
              >
                <IconRefresh size={14} />
              </ActionIcon>
            </Group>
            <ScrollArea h={400} viewportRef={logScrollRef}>
              <Code block style={{ fontSize: 11, background: 'transparent', whiteSpace: 'pre-wrap', color: 'var(--mantine-color-gray-3)' }}>
                {containerLogs || 'No logs available.'}
              </Code>
            </ScrollArea>
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="config" pt="md">
          <Stack gap="md">
            {metadata?.mounts && metadata.mounts.length > 0 && (
              <Paper withBorder p="md" radius="md" maw={600}>
                <Title order={5} mb="sm">Mounts</Title>
                <Stack gap={4}>
                  {metadata.mounts.map((m) => (
                    <Group key={m.target} gap="xs">
                      <Badge size="xs" variant="light" color="violet">{m.type}</Badge>
                      <Text size="xs" ff="monospace" c="dimmed">{m.source}</Text>
                      <Text size="xs" c="dimmed">&rarr;</Text>
                      <Text size="xs" ff="monospace">{m.target}</Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>
            )}
            {metadata?.devcontainer ? (
              <Paper withBorder p="md" radius="md" maw={600}>
                <Title order={5} mb="sm">devcontainer.json</Title>
                <Code block style={{ fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                  {JSON.stringify(metadata.devcontainer, null, 2)}
                </Code>
              </Paper>
            ) : (
              <Text c="dimmed">No devcontainer configuration available.</Text>
            )}
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Group>
        <Button
          color="orange"
          variant="light"
          leftSection={<IconEraser size={16} />}
          onClick={handleCleanupWorkspace}
          loading={cleaningUp}
        >
          Clean Workspace
        </Button>
        <Button
          color="red"
          variant="light"
          leftSection={<IconTrash size={16} />}
          onClick={handleDestroy}
          loading={destroyMutation.isPending}
        >
          Destroy Sandbox
        </Button>
      </Group>
    </Stack>
  );
}
