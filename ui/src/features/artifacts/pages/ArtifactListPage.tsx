import {
  Title, Stack, Table, Loader, Center, Badge, Text, Tabs, Group, TextInput,
  Modal, ScrollArea, Progress, TypographyStylesProvider, Anchor, ActionIcon,
} from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  useArtifactsListArtifacts,
  useArtifactsListTestResults,
  getArtifactsListArtifactsQueryKey,
  getArtifactsListTestResultsQueryKey,
} from '@/generated/api/artifacts/artifacts';
import { customInstance } from '@/shared/api/client';
import { DiffView } from '@/shared/components/DiffView';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';
import '@/features/chat/chat-markdown.css';

const artifactTypeColor: Record<string, string> = {
  diff: 'blue',
  research_report: 'teal',
  plan: 'violet',
};


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
  const queryClient = useQueryClient();
  const { data: artifactsResp, isLoading: artLoading } = useArtifactsListArtifacts();
  const { data: testsResp, isLoading: testsLoading } = useArtifactsListTestResults();
  const [filter, setFilter] = useState('');
  const [viewArtifact, setViewArtifact] = useState<ArtifactItem | null>(null);

  const deleteArtifact = async (artifactId: string) => {
    await customInstance(`/api/v1/artifacts/${artifactId}`, { method: 'DELETE' });
    queryClient.invalidateQueries({ queryKey: getArtifactsListArtifactsQueryKey() });
  };

  const deleteTestResult = async (resultId: string) => {
    await customInstance(`/api/v1/test-results/${resultId}`, { method: 'DELETE' });
    queryClient.invalidateQueries({ queryKey: getArtifactsListTestResultsQueryKey() });
  };

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
                  <Table.Th w={50} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredArtifacts.map((a) => (
                  <Table.Tr key={a.artifact_id} style={{ cursor: 'pointer' }} onClick={() => setViewArtifact(a)}>
                    <Table.Td><code>{a.path || a.artifact_id}</code></Table.Td>
                    <Table.Td><Badge variant="light" color={artifactTypeColor[a.artifact_type] ?? 'gray'}>{a.artifact_type}</Badge></Table.Td>
                    <Table.Td>
                      <Anchor component={Link} to={`/pipelines/${a.run_id}`} size="xs" ff="monospace">
                        {a.run_id}
                      </Anchor>
                    </Table.Td>
                    <Table.Td><TimeAgo date={a.created_at || (a.metadata as Record<string, unknown>)?.created_at as string} size="sm" /></Table.Td>
                    <Table.Td>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); deleteArtifact(a.artifact_id); }}
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Table.Td>
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
                  <Table.Th w={50} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredTests.map((t) => {
                  const passRate = t.total > 0 ? Math.round((t.passed / t.total) * 100) : 0;
                  return (
                    <Table.Tr key={t.result_id}>
                      <Table.Td>
                        <Anchor component={Link} to={`/pipelines/${t.run_id}`} size="xs" ff="monospace">
                          {t.run_id}
                        </Anchor>
                      </Table.Td>
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
                      <Table.Td>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          size="sm"
                          onClick={() => deleteTestResult(t.result_id)}
                        >
                          <IconTrash size={14} />
                        </ActionIcon>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>
      </Tabs>

      <Modal opened={!!viewArtifact} onClose={() => setViewArtifact(null)} title={viewArtifact?.path || viewArtifact?.artifact_type || 'Artifact'} fullScreen>
        {viewArtifact && (
          <Stack gap="sm" h="100%">
            <Group gap="md">
              <Badge color={artifactTypeColor[viewArtifact.artifact_type] ?? 'gray'}>{viewArtifact.artifact_type}</Badge>
              <Anchor component={Link} to={`/pipelines/${viewArtifact.run_id}`} size="sm">
                Run: {viewArtifact.run_id}
              </Anchor>
              <Text size="sm" c="dimmed">Work Item: {viewArtifact.work_item_id?.slice(0, 8)}</Text>
            </Group>
            <ScrollArea style={{ flex: 1 }}>
              {viewArtifact.artifact_type === 'diff' ? (
                <DiffView content={viewArtifact.content} />
              ) : (
                <TypographyStylesProvider>
                  <div className="chat-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{viewArtifact.content || 'No content'}</ReactMarkdown>
                  </div>
                </TypographyStylesProvider>
              )}
            </ScrollArea>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
