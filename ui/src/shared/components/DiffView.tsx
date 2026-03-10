import { useState } from 'react';
import {
  Paper, Text, Group, Badge, Stack, ScrollArea, UnstyledButton, Collapse,
  Modal, ActionIcon, Box, Tooltip,
  useMantineColorScheme,
} from '@mantine/core';
import { IconChevronRight, IconFile, IconMaximize } from '@tabler/icons-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface DiffLine {
  type: 'file-header' | 'hunk' | 'addition' | 'deletion' | 'context';
  text: string;
}

interface FileDiff {
  path: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
}

// ── Parser ───────────────────────────────────────────────────────────────────

function parseDiff(content: string): FileDiff[] {
  const rawLines = content.split('\n');
  const files: FileDiff[] = [];
  let current: FileDiff | null = null;

  for (const raw of rawLines) {
    if (raw.startsWith('diff --git')) {
      const match = raw.match(/b\/(.+)$/);
      current = { path: match?.[1] ?? '', additions: 0, deletions: 0, lines: [] };
      files.push(current);
    } else if (raw.startsWith('---') || raw.startsWith('+++')) {
      // skip file-header meta lines (already have the path)
    } else if (raw.startsWith('@@')) {
      current?.lines.push({ type: 'hunk', text: raw });
    } else if (raw.startsWith('+')) {
      if (current) current.additions++;
      current?.lines.push({ type: 'addition', text: raw });
    } else if (raw.startsWith('-')) {
      if (current) current.deletions++;
      current?.lines.push({ type: 'deletion', text: raw });
    } else {
      current?.lines.push({ type: 'context', text: raw });
    }
  }

  return files;
}

// ── Styles ───────────────────────────────────────────────────────────────────

const lightLineStyle: Record<DiffLine['type'], React.CSSProperties> = {
  'file-header': { background: '#f0f0f8', color: '#555', fontWeight: 600 },
  hunk: { background: '#f0f0ff', color: '#6a6aaa' },
  addition: { background: '#e6ffec', color: '#1a7f37' },
  deletion: { background: '#ffebe9', color: '#cf222e' },
  context: { background: 'transparent', color: '#656d76' },
};

const darkLineStyle: Record<DiffLine['type'], React.CSSProperties> = {
  'file-header': { background: 'rgba(110, 118, 129, 0.1)', color: '#adbac7', fontWeight: 600 },
  hunk: { background: 'rgba(56, 139, 253, 0.08)', color: '#6cb6ff' },
  addition: { background: 'rgba(46, 160, 67, 0.12)', color: '#56d364' },
  deletion: { background: 'rgba(248, 81, 73, 0.12)', color: '#f47067' },
  context: { background: 'transparent', color: '#8b949e' },
};

const MONO_FONT = 'ui-monospace, SFMono-Regular, Menlo, monospace';

// ── Diff lines renderer ─────────────────────────────────────────────────────

function DiffLines({
  lines,
  lineStyle,
  fontSize = '0.75rem',
}: {
  lines: DiffLine[];
  lineStyle: Record<DiffLine['type'], React.CSSProperties>;
  fontSize?: string;
}) {
  return (
    <pre
      style={{
        margin: 0,
        padding: 8,
        fontSize,
        lineHeight: 1.6,
        fontFamily: MONO_FONT,
      }}
    >
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            ...lineStyle[line.type],
            padding: '0 8px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {line.text}
        </div>
      ))}
    </pre>
  );
}

// ── File section (inline collapsible) ────────────────────────────────────────

function FileSection({
  file,
  lineStyle,
  defaultOpen,
}: {
  file: FileDiff;
  lineStyle: Record<DiffLine['type'], React.CSSProperties>;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Paper withBorder radius="sm" style={{ overflow: 'hidden' }}>
      <UnstyledButton
        onClick={() => setOpen((v) => !v)}
        style={{ width: '100%' }}
        px="sm"
        py={8}
      >
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
            <IconChevronRight
              size={14}
              stroke={2}
              style={{
                transition: 'transform 200ms ease',
                transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
                flexShrink: 0,
                opacity: 0.5,
              }}
            />
            <IconFile size={14} style={{ flexShrink: 0, opacity: 0.5 }} />
            <Text size="xs" ff="monospace" fw={500} truncate style={{ minWidth: 0 }}>
              {file.path}
            </Text>
          </Group>
          <Group gap={6} style={{ flexShrink: 0 }}>
            {file.additions > 0 && (
              <Text size="xs" c="green" fw={600}>+{file.additions}</Text>
            )}
            {file.deletions > 0 && (
              <Text size="xs" c="red" fw={600}>-{file.deletions}</Text>
            )}
          </Group>
        </Group>
      </UnstyledButton>

      <Collapse in={open}>
        <ScrollArea.Autosize mah={400} type="auto">
          <DiffLines lines={file.lines} lineStyle={lineStyle} />
        </ScrollArea.Autosize>
      </Collapse>
    </Paper>
  );
}

// ── Fullscreen modal ─────────────────────────────────────────────────────────

function DiffModal({
  files,
  lineStyle,
  opened,
  onClose,
}: {
  files: FileDiff[];
  lineStyle: Record<DiffLine['type'], React.CSSProperties>;
  opened: boolean;
  onClose: () => void;
}) {
  const [activeFile, setActiveFile] = useState(0);
  const totalAdditions = files.reduce((s, f) => s + f.additions, 0);
  const totalDeletions = files.reduce((s, f) => s + f.deletions, 0);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      fullScreen
      title={
        <Group gap="sm">
          <Text fw={600}>Code Changes</Text>
          <Badge variant="light" color="gray" size="sm">
            {files.length} file{files.length !== 1 ? 's' : ''}
          </Badge>
          {totalAdditions > 0 && (
            <Badge variant="light" color="green" size="sm">+{totalAdditions}</Badge>
          )}
          {totalDeletions > 0 && (
            <Badge variant="light" color="red" size="sm">-{totalDeletions}</Badge>
          )}
        </Group>
      }
      styles={{
        body: { padding: 0, display: 'flex', height: 'calc(100vh - 60px)' },
        header: { borderBottom: '1px solid var(--mantine-color-dark-4)' },
      }}
    >
      {/* File sidebar */}
      <Box
        style={(theme) => ({
          width: 280,
          flexShrink: 0,
          borderRight: `1px solid ${theme.colors.dark[4]}`,
          display: 'flex',
          flexDirection: 'column',
        })}
      >
        <ScrollArea style={{ flex: 1 }} offsetScrollbars>
          {files.map((file, i) => (
            <UnstyledButton
              key={file.path}
              onClick={() => setActiveFile(i)}
              px="sm"
              py={8}
              style={(theme) => ({
                width: '100%',
                display: 'block',
                background: i === activeFile
                  ? theme.colors.dark[5]
                  : 'transparent',
                borderLeft: i === activeFile
                  ? `2px solid ${theme.colors.blue[5]}`
                  : '2px solid transparent',
              })}
            >
              <Group justify="space-between" wrap="nowrap">
                <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                  <IconFile size={14} style={{ flexShrink: 0, opacity: 0.5 }} />
                  <Text size="xs" ff="monospace" truncate style={{ minWidth: 0 }}>
                    {file.path.split('/').pop()}
                  </Text>
                </Group>
                <Group gap={4} style={{ flexShrink: 0 }}>
                  {file.additions > 0 && (
                    <Text size="xs" c="green">+{file.additions}</Text>
                  )}
                  {file.deletions > 0 && (
                    <Text size="xs" c="red">-{file.deletions}</Text>
                  )}
                </Group>
              </Group>
              <Text size="xs" c="dimmed" ff="monospace" truncate mt={2}>
                {file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : ''}
              </Text>
            </UnstyledButton>
          ))}
        </ScrollArea>
      </Box>

      {/* Diff content */}
      <Box style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {files[activeFile] && (
          <>
            <Group
              px="md"
              py={8}
              style={(theme) => ({
                borderBottom: `1px solid ${theme.colors.dark[4]}`,
                flexShrink: 0,
              })}
            >
              <Text size="sm" ff="monospace" fw={500}>
                {files[activeFile]!.path}
              </Text>
            </Group>
            <ScrollArea style={{ flex: 1 }}>
              <DiffLines
                lines={files[activeFile]!.lines}
                lineStyle={lineStyle}
                fontSize="0.8rem"
              />
            </ScrollArea>
          </>
        )}
      </Box>
    </Modal>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

interface DiffViewProps {
  content: string;
  maxHeight?: number;
}

export function DiffView({ content }: DiffViewProps) {
  const { colorScheme } = useMantineColorScheme();
  const lineStyle = colorScheme === 'dark' ? darkLineStyle : lightLineStyle;
  const [modalOpen, setModalOpen] = useState(false);

  if (!content?.trim()) {
    return <Text size="sm" c="dimmed">No changes</Text>;
  }

  const files = parseDiff(content);
  const totalAdditions = files.reduce((s, f) => s + f.additions, 0);
  const totalDeletions = files.reduce((s, f) => s + f.deletions, 0);

  return (
    <>
      <Stack gap="xs">
        {/* Stat summary + expand button */}
        <Group justify="space-between">
          <Group gap="sm" wrap="wrap">
            <Badge variant="light" color="gray" size="sm">
              {files.length} file{files.length !== 1 ? 's' : ''} changed
            </Badge>
            {totalAdditions > 0 && (
              <Badge variant="light" color="green" size="sm">
                +{totalAdditions}
              </Badge>
            )}
            {totalDeletions > 0 && (
              <Badge variant="light" color="red" size="sm">
                -{totalDeletions}
              </Badge>
            )}
          </Group>
          <Tooltip label="Fullscreen diff viewer">
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={() => setModalOpen(true)}
            >
              <IconMaximize size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>

        {/* Per-file collapsible diffs */}
        {files.map((file) => (
          <FileSection
            key={file.path}
            file={file}
            lineStyle={lineStyle}
            defaultOpen={files.length <= 3}
          />
        ))}
      </Stack>

      <DiffModal
        files={files}
        lineStyle={lineStyle}
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
}
