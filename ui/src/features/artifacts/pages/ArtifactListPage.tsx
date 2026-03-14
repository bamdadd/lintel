import {
  Title, Stack, Table, Loader, Center, Badge, Text, Tabs, Group, TextInput,
  Modal, ScrollArea, Code, Progress, TypographyStylesProvider,
} from '@mantine/core';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  useArtifactsListArtifacts,
  useArtifactsListTestResults,
} from '@/generated/api/artifacts/artifacts';
import { DiffView } from '@/shared/components/DiffView';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';
import '@/features/chat/chat-markdown.css';

const artifactTypeColor: Record<string, string> = {
  diff: 'blue',
  research_report: 'teal',
  plan: 'violet',
};

const markdownTypes = new Set(['research_report', 'plan']);

interface ArtifactItem {
  artifact_id: string;
  work_item_id: string;
  run_id: string;
  artifact_type: string;
  path: string;
  content: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

interface TestResultItem {
  result_id: string;
  run_id: string;
  stage_id: string;
  verdict: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  created_at: string;
}

const verdictColor: Record<string, string> = { passed: 'green', failed: 'red', error: 'orange', skipped: 'gray' };

export function Component() {
  const { data: artifactsResp, isLoading: artLoading } = useArtifactsListArtifacts();
  const { data: testsResp, isLoading: testsLoading } = useArtifactsListTestResults();
  const [filter, setFilter] = useState('');
  const [viewArtifact, setViewArtifact] = useState<ArtifactItem | null>(null);

  if (artLoading || testsLoading) return <Center py="xl"><Loader /></Center>;

  const artifacts = (artifactsResp?.data ?? []) as ArtifactItem[];
  const testResults = (testsResp?.data ?? []) as TestResultItem[];

  const filteredArtifacts = artifacts.filter((a) =>
    a.path?.toLowerCase().includes(filter.toLowerCase())
    || a.artifact_type?.toLowerCase().includes(filter.toLowerCase())
    || a.run_id?.toLowerCase().includes(filter.toLowerCase())
  );

  const filteredTests = testResults.filter((t) =>
    t.verdict?.toLowerCase().includes(filter.toLowerCase())
    || t.run_id?.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Artifacts & Test Results</Title>
        <TextInput placeholder="Filter..." value={filter} onChange={(e) => setFilter(e.currentTarget.value)} style={{ width: 250 }} />
      </Group>

      <Tabs defaultValue="artifacts">
        <Tabs.List>
          <Tabs.Tab value="artifacts">Code Artifacts ({artifacts.length})</Tabs.Tab>
          <Tabs.Tab value="tests">Test Results ({testResults.length})</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="artifacts" pt="sm">
          {artifacts.length === 0 ? (
            <EmptyState title="No artifacts" description="Artifacts are generated during pipeline runs" />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Path</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Run</Table.Th>
                  <Table.Th>Created</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredArtifacts.map((a) => (
                  <Table.Tr key={a.artifact_id} style={{ cursor: 'pointer' }} onClick={() => setViewArtifact(a)}>
                    <Table.Td><code>{a.path || a.artifact_id}</code></Table.Td>
                    <Table.Td><Badge variant="light" color={artifactTypeColor[a.artifact_type] ?? 'gray'}>{a.artifact_type}</Badge></Table.Td>
                    <Table.Td><Text size="xs" c="dimmed">{a.run_id?.slice(0, 8)}</Text></Table.Td>
                    <Table.Td><TimeAgo date={a.created_at} size="sm" /></Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="tests" pt="sm">
          {testResults.length === 0 ? (
            <EmptyState title="No test results" description="Test results appear after pipeline stages complete" />
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Run</Table.Th>
                  <Table.Th>Stage</Table.Th>
                  <Table.Th>Verdict</Table.Th>
                  <Table.Th>Results</Table.Th>
                  <Table.Th>Pass Rate</Table.Th>
                  <Table.Th>Created</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredTests.map((t) => {
                  const passRate = t.total > 0 ? Math.round((t.passed / t.total) * 100) : 0;
                  return (
                    <Table.Tr key={t.result_id}>
                      <Table.Td><Text size="xs" ff="monospace">{t.run_id?.slice(0, 8)}</Text></Table.Td>
                      <Table.Td><Text size="xs" ff="monospace">{t.stage_id?.slice(0, 8)}</Text></Table.Td>
                      <Table.Td><Badge color={verdictColor[t.verdict] ?? 'gray'}>{t.verdict}</Badge></Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          <Badge size="sm" color="green" variant="light">{t.passed} pass</Badge>
                          {t.failed > 0 && <Badge size="sm" color="red" variant="light">{t.failed} fail</Badge>}
                          {t.errors > 0 && <Badge size="sm" color="orange" variant="light">{t.errors} err</Badge>}
                          {t.skipped > 0 && <Badge size="sm" color="gray" variant="light">{t.skipped} skip</Badge>}
                        </Group>
                      </Table.Td>
                      <Table.Td style={{ width: 120 }}>
                        <Progress value={passRate} color={passRate === 100 ? 'green' : passRate > 80 ? 'yellow' : 'red'} size="sm" />
                        <Text size="xs" ta="center">{passRate}%</Text>
                      </Table.Td>
                      <Table.Td><TimeAgo date={t.created_at} size="sm" /></Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>
      </Tabs>

      <Modal opened={!!viewArtifact} onClose={() => setViewArtifact(null)} title={viewArtifact?.path || viewArtifact?.artifact_type || 'Artifact'} size="xl">
        {viewArtifact && (
          <Stack gap="sm">
            <Group gap="md">
              <Badge color={artifactTypeColor[viewArtifact.artifact_type] ?? 'gray'}>{viewArtifact.artifact_type}</Badge>
              <Text size="sm" c="dimmed">Run: {viewArtifact.run_id}</Text>
              <Text size="sm" c="dimmed">Work Item: {viewArtifact.work_item_id}</Text>
            </Group>
            <ScrollArea h={400}>
              {viewArtifact.artifact_type === 'diff' ? (
                <DiffView content={viewArtifact.content} maxHeight={380} />
              ) : markdownTypes.has(viewArtifact.artifact_type) ? (
                <TypographyStylesProvider>
                  <div className="chat-markdown">
                    <ReactMarkdown>{viewArtifact.content || 'No content'}</ReactMarkdown>
                  </div>
                </TypographyStylesProvider>
              ) : (
                <Code block>{viewArtifact.content || 'No content'}</Code>
              )}
            </ScrollArea>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
