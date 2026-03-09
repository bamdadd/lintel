import { Paper, Text, Group, Badge, Stack, ScrollArea } from '@mantine/core';

interface FileStat {
  path: string;
  additions: number;
  deletions: number;
}

function parseDiff(content: string): { files: FileStat[]; lines: DiffLine[] } {
  const lines = content.split('\n');
  const files: FileStat[] = [];
  const diffLines: DiffLine[] = [];
  let currentFile: FileStat | null = null;

  for (const raw of lines) {
    if (raw.startsWith('diff --git')) {
      const match = raw.match(/b\/(.+)$/);
      currentFile = { path: match?.[1] ?? '', additions: 0, deletions: 0 };
      files.push(currentFile);
      diffLines.push({ type: 'file-header', text: raw });
    } else if (raw.startsWith('---') || raw.startsWith('+++')) {
      diffLines.push({ type: 'file-header', text: raw });
    } else if (raw.startsWith('@@')) {
      diffLines.push({ type: 'hunk', text: raw });
    } else if (raw.startsWith('+')) {
      if (currentFile) currentFile.additions++;
      diffLines.push({ type: 'addition', text: raw });
    } else if (raw.startsWith('-')) {
      if (currentFile) currentFile.deletions++;
      diffLines.push({ type: 'deletion', text: raw });
    } else {
      diffLines.push({ type: 'context', text: raw });
    }
  }

  return { files, lines: diffLines };
}

interface DiffLine {
  type: 'file-header' | 'hunk' | 'addition' | 'deletion' | 'context';
  text: string;
}

const lineStyle: Record<DiffLine['type'], React.CSSProperties> = {
  'file-header': { background: '#f0f0f8', color: '#555', fontWeight: 600 },
  hunk: { background: '#f0f0ff', color: '#6a6aaa' },
  addition: { background: '#e6ffec', color: '#1a7f37' },
  deletion: { background: '#ffebe9', color: '#cf222e' },
  context: { background: 'transparent', color: '#656d76' },
};

interface DiffViewProps {
  content: string;
  maxHeight?: number;
}

export function DiffView({ content, maxHeight = 500 }: DiffViewProps) {
  if (!content?.trim()) {
    return <Text size="sm" c="dimmed">No changes</Text>;
  }

  const { files, lines } = parseDiff(content);
  const totalAdditions = files.reduce((s, f) => s + f.additions, 0);
  const totalDeletions = files.reduce((s, f) => s + f.deletions, 0);

  return (
    <Stack gap="xs">
      {/* Stat summary */}
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

      {/* File list */}
      {files.length > 1 && (
        <Group gap={4} wrap="wrap">
          {files.map((f) => (
            <Text key={f.path} size="xs" ff="monospace" c="dimmed">
              {f.path}{' '}
              <Text span c="green" size="xs">+{f.additions}</Text>{' '}
              <Text span c="red" size="xs">-{f.deletions}</Text>
            </Text>
          ))}
        </Group>
      )}

      {/* Diff content */}
      <Paper withBorder style={{ overflow: 'hidden' }}>
        <ScrollArea h={maxHeight} type="auto">
          <pre style={{ margin: 0, padding: 8, fontSize: '0.75rem', lineHeight: 1.5, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
            {lines.map((line, i) => (
              <div key={i} style={{ ...lineStyle[line.type], padding: '0 8px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {line.text}
              </div>
            ))}
          </pre>
        </ScrollArea>
      </Paper>
    </Stack>
  );
}
