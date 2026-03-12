import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, Code, Paper, Text,
  SimpleGrid, ThemeIcon, Progress,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconBrain, IconCode, IconPlugConnected,
  IconDatabase, IconApi, IconSettings, IconGitBranch,
} from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { knowledgeEntryHooks, knowledgeExtractionHooks } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface KnowledgeItem {
  entry_id: string; project_id: string; name: string; entry_type: string;
  description: string; source_file: string; source_repo: string; source_lines: string;
  dependencies: string[]; code_snippet: string; extracted_at: string;
  status: string; tags: string[];
}
interface ExtractionRun {
  run_id: string; project_id: string; repo_id: string; status: string;
  total_files: number; processed_files: number; entries_found: number;
  started_at: string; completed_at: string; error: string;
}
interface ProjectItem { project_id: string; name: string; }

const TYPE_OPTIONS = [
  { value: 'logic_flow', label: 'Logic Flow' },
  { value: 'event_handler', label: 'Event Handler' },
  { value: 'integration', label: 'Integration' },
  { value: 'data_model', label: 'Data Model' },
  { value: 'api_endpoint', label: 'API Endpoint' },
  { value: 'business_rule', label: 'Business Rule' },
  { value: 'configuration', label: 'Configuration' },
  { value: 'dependency', label: 'Dependency' },
];

const typeIcons: Record<string, typeof IconBrain> = {
  logic_flow: IconGitBranch, event_handler: IconBrain, integration: IconPlugConnected,
  data_model: IconDatabase, api_endpoint: IconApi, business_rule: IconBrain,
  configuration: IconSettings, dependency: IconCode,
};

const typeColors: Record<string, string> = {
  logic_flow: 'blue', event_handler: 'violet', integration: 'cyan',
  data_model: 'green', api_endpoint: 'orange', business_rule: 'pink',
  configuration: 'gray', dependency: 'indigo',
};

const statusColor: Record<string, string> = {
  pending: 'gray', in_progress: 'blue', completed: 'green', failed: 'red', stale: 'yellow',
};

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('');

  const { data: resp, isLoading } = knowledgeEntryHooks.useList(filterProject || undefined);
  const { data: extractResp } = knowledgeExtractionHooks.useList(filterProject || undefined);
  const createMut = knowledgeEntryHooks.useCreate();
  const removeMut = knowledgeEntryHooks.useRemove();
  const startExtraction = knowledgeExtractionHooks.useCreate();
  const [creating, setCreating] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<KnowledgeItem | null>(null);

  const form = useForm({
    initialValues: {
      name: '', project_id: '', entry_type: 'logic_flow', description: '',
      source_file: '', source_repo: '', source_lines: '', code_snippet: '',
      tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;
  const allItems = (resp?.data ?? []) as unknown as KnowledgeItem[];
  const items = filterType ? allItems.filter((i) => i.entry_type === filterType) : allItems;
  const extractions = (extractResp?.data ?? []) as unknown as ExtractionRun[];

  // Group by type for stat cards
  const typeCounts: Record<string, number> = {};
  for (const item of allItems) {
    typeCounts[item.entry_type] = (typeCounts[item.entry_type] ?? 0) + 1;
  }

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => { notifications.show({ title: 'Created', message: 'Knowledge entry added', color: 'green' }); form.reset(); setCreating(false); },
    });
  });

  const handleStartExtraction = () => {
    if (!filterProject) {
      notifications.show({ title: 'Error', message: 'Select a project first', color: 'red' });
      return;
    }
    startExtraction.mutate({ project_id: filterProject } as any, {
      onSuccess: () => notifications.show({ title: 'Started', message: 'Knowledge extraction started', color: 'blue' }),
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Knowledge Base</Title>
        <Group>
          <Select placeholder="Filter by project" data={[{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))]} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Select placeholder="All types" data={[{ value: '', label: 'All Types' }, ...TYPE_OPTIONS]} value={filterType} onChange={(v) => setFilterType(v ?? '')} clearable w={180} />
          <Button variant="light" onClick={handleStartExtraction} loading={startExtraction.isPending} disabled={!filterProject}>
            Extract from Code
          </Button>
          <Button onClick={() => setCreating(true)}>Add Entry</Button>
        </Group>
      </Group>

      {/* Type distribution */}
      {allItems.length > 0 && (
        <SimpleGrid cols={{ base: 2, sm: 4, lg: 8 }}>
          {TYPE_OPTIONS.map((t) => {
            const Icon = typeIcons[t.value] ?? IconBrain;
            return (
              <Paper
                key={t.value}
                withBorder p="xs" radius="md"
                style={{ cursor: 'pointer', opacity: filterType && filterType !== t.value ? 0.5 : 1 }}
                onClick={() => setFilterType(filterType === t.value ? '' : t.value)}
              >
                <Group gap="xs">
                  <ThemeIcon size="sm" color={typeColors[t.value]} variant="light"><Icon size={14} /></ThemeIcon>
                  <div>
                    <Text size="sm" fw={600}>{typeCounts[t.value] ?? 0}</Text>
                    <Text size="xs" c="dimmed">{t.label}</Text>
                  </div>
                </Group>
              </Paper>
            );
          })}
        </SimpleGrid>
      )}

      {/* Active extractions */}
      {extractions.length > 0 && (
        <Paper withBorder p="md" radius="md">
          <Text fw={600} mb="xs">Extraction Runs</Text>
          {extractions.map((run) => (
            <Group key={run.run_id} justify="space-between" mb="xs">
              <Group gap="xs">
                <Badge color={statusColor[run.status]} size="sm">{run.status}</Badge>
                <Text size="sm">{run.repo_id || 'All repos'}</Text>
              </Group>
              <Group gap="xs">
                <Text size="xs" c="dimmed">{run.entries_found} entries found</Text>
                {run.total_files > 0 && (
                  <Progress value={(run.processed_files / run.total_files) * 100} w={100} size="sm" />
                )}
              </Group>
            </Group>
          ))}
        </Paper>
      )}

      {items.length === 0 ? (
        <EmptyState
          title="No knowledge entries"
          description="Extract knowledge from your codebase or add entries manually. Captures logic flows, integrations, data models, and more."
          actionLabel="Add Entry"
          onAction={() => setCreating(true)}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead><Table.Tr>
            <Table.Th>Type</Table.Th><Table.Th>Name</Table.Th><Table.Th>Source</Table.Th>
            <Table.Th>Status</Table.Th><Table.Th />
          </Table.Tr></Table.Thead>
          <Table.Tbody>
            {items.map((item) => {
              const Icon = typeIcons[item.entry_type] ?? IconBrain;
              return (
                <Table.Tr key={item.entry_id} style={{ cursor: 'pointer' }} onClick={() => setSelectedEntry(item)}>
                  <Table.Td>
                    <Badge leftSection={<Icon size={12} />} color={typeColors[item.entry_type]} variant="light" size="sm">
                      {item.entry_type.replace('_', ' ')}
                    </Badge>
                  </Table.Td>
                  <Table.Td fw={500}>{item.name}</Table.Td>
                  <Table.Td><Text size="xs" c="dimmed" truncate maw={200}>{item.source_file || '—'}</Text></Table.Td>
                  <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                  <Table.Td>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); removeMut.mutate(item.entry_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      {/* Detail view */}
      <Modal opened={!!selectedEntry} onClose={() => setSelectedEntry(null)} title={selectedEntry?.name ?? ''} size="xl">
        {selectedEntry && (
          <Stack gap="sm">
            <Group>
              <Badge color={typeColors[selectedEntry.entry_type]} variant="light">{selectedEntry.entry_type.replace('_', ' ')}</Badge>
              <Badge color={statusColor[selectedEntry.status]} variant="light">{selectedEntry.status}</Badge>
            </Group>
            {selectedEntry.description && <Text size="sm">{selectedEntry.description}</Text>}
            <Group gap="xs">
              <Text size="sm" fw={600}>Source:</Text>
              <Text size="sm">{selectedEntry.source_file || '—'}</Text>
              {selectedEntry.source_lines && <Text size="sm" c="dimmed">lines {selectedEntry.source_lines}</Text>}
            </Group>
            {selectedEntry.source_repo && (
              <Group gap="xs"><Text size="sm" fw={600}>Repository:</Text><Text size="sm">{selectedEntry.source_repo}</Text></Group>
            )}
            {selectedEntry.code_snippet && (
              <>
                <Text size="sm" fw={600}>Code:</Text>
                <Code block>{selectedEntry.code_snippet}</Code>
              </>
            )}
            {(selectedEntry.dependencies ?? []).length > 0 && (
              <>
                <Text size="sm" fw={600}>Dependencies:</Text>
                <Group gap="xs">
                  {selectedEntry.dependencies.map((d) => <Badge key={d} size="xs" variant="outline">{d}</Badge>)}
                </Group>
              </>
            )}
          </Stack>
        )}
      </Modal>

      {/* Create modal */}
      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Knowledge Entry" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Select label="Project" data={projects.map((p) => ({ value: p.project_id, label: p.name }))} searchable {...form.getInputProps('project_id')} />
            <Select label="Type" data={TYPE_OPTIONS} {...form.getInputProps('entry_type')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <TextInput label="Source File" placeholder="src/main.py" {...form.getInputProps('source_file')} />
            <Group grow>
              <TextInput label="Repository" {...form.getInputProps('source_repo')} />
              <TextInput label="Lines" placeholder="10-50" {...form.getInputProps('source_lines')} />
            </Group>
            <Textarea label="Code Snippet" autosize minRows={3} {...form.getInputProps('code_snippet')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
