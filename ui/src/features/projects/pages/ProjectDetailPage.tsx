import { useParams, useNavigate } from 'react-router';
import { useState } from 'react';
import {
  Title, Stack, Paper, Text, Group, Button, Badge, Loader, Center,
  TextInput, MultiSelect, Select, Modal, Tabs, SimpleGrid, ThemeIcon,
  RingProgress, Card, Tooltip,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  IconShieldCheck, IconFileText, IconListDetails, IconTool,
  IconTarget, IconChartBar, IconFlask, IconBrain, IconArrowRight,
} from '@tabler/icons-react';
import {
  useProjectsGetProject,
  useProjectsUpdateProject,
  useProjectsRemoveProject,
} from '@/generated/api/projects/projects';
import { useRepositoriesListRepositories } from '@/generated/api/repositories/repositories';
import { useAiProvidersListAiProviders } from '@/generated/api/ai-providers/ai-providers';
import { useComplianceOverview } from '@/features/compliance/api';

interface ProjectData {
  project_id: string;
  name: string;
  repo_ids: string[];
  channel_id: string;
  workspace_id: string;
  workflow_definition_id: string;
  default_branch: string;
  ai_provider_id: string;
  status: string;
}

interface RepoItem { repo_id: string; name: string; }
interface ProviderItem { provider_id: string; name: string; }

const riskColors: Record<string, string> = { low: 'green', medium: 'yellow', high: 'orange', critical: 'red' };
const statusColors: Record<string, string> = { draft: 'gray', active: 'green', under_review: 'yellow', deprecated: 'orange', non_compliant: 'red' };

export function Component() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);

  const { data: resp, isLoading } = useProjectsGetProject(projectId ?? '', {
    query: { enabled: !!projectId },
  });
  const { data: reposResp } = useRepositoriesListRepositories();
  const { data: providersResp } = useAiProvidersListAiProviders();
  const { data: complianceResp } = useComplianceOverview(projectId ?? '');
  const updateMut = useProjectsUpdateProject();
  const deleteMut = useProjectsRemoveProject();

  const repos = (reposResp?.data ?? []) as unknown as RepoItem[];
  const providers = (providersResp?.data ?? []) as unknown as ProviderItem[];
  const repoOptions = repos.map((r) => ({ value: r.repo_id, label: r.name }));
  const providerOptions = [{ value: '', label: '— None —' }, ...providers.map((p) => ({ value: p.provider_id, label: p.name }))];

  const overview = complianceResp?.data as Record<string, unknown> | undefined;
  const counts = (overview?.counts ?? {}) as Record<string, number>;
  const riskDist = (overview?.risk_distribution ?? {}) as Record<string, number>;
  const cascade = (overview?.cascade ?? {}) as Record<string, Record<string, unknown>[]>;

  const form = useForm({
    initialValues: { name: '', repo_ids: [] as string[], default_branch: '', channel_id: '', workspace_id: '', ai_provider_id: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const project = resp?.data as ProjectData | undefined;
  if (!project) return <Text>Project not found</Text>;

  const repoNames = (project.repo_ids ?? []).map(
    (id) => repos.find((r) => r.repo_id === id)?.name ?? id,
  );
  const providerName = providers.find((p) => p.provider_id === project.ai_provider_id)?.name ?? project.ai_provider_id;

  const startEdit = () => {
    form.setValues({
      name: project.name,
      repo_ids: project.repo_ids ?? [],
      default_branch: project.default_branch ?? 'main',
      channel_id: project.channel_id ?? '',
      workspace_id: project.workspace_id ?? '',
      ai_provider_id: project.ai_provider_id ?? '',
    });
    setEditing(true);
  };

  const handleSave = form.onSubmit((values) => {
    updateMut.mutate(
      { projectId: project.project_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Project updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/projects'] });
          setEditing(false);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' }),
      },
    );
  });

  const handleDelete = () => {
    deleteMut.mutate(
      { projectId: project.project_id },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Project removed', color: 'orange' });
          void navigate('/projects');
        },
      },
    );
  };

  const totalRisk = Object.values(riskDist).reduce((a, b) => a + b, 0) || 1;

  const complianceCards = [
    { label: 'Regulations', count: counts.regulations ?? 0, icon: IconShieldCheck, color: 'blue' },
    { label: 'Policies', count: counts.policies ?? 0, icon: IconFileText, color: 'violet' },
    { label: 'Procedures', count: counts.procedures ?? 0, icon: IconListDetails, color: 'indigo' },
    { label: 'Practices', count: counts.practices ?? 0, icon: IconTool, color: 'teal' },
    { label: 'Strategies', count: counts.strategies ?? 0, icon: IconTarget, color: 'cyan' },
    { label: 'KPIs', count: counts.kpis ?? 0, icon: IconChartBar, color: 'green' },
    { label: 'Experiments', count: counts.experiments ?? 0, icon: IconFlask, color: 'orange' },
    { label: 'Knowledge', count: counts.knowledge_entries ?? 0, icon: IconBrain, color: 'grape' },
  ];

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/projects')}>&larr; Back</Button>
        <Title order={2}>{project.name}</Title>
        <Badge>{project.status}</Badge>
      </Group>

      <Tabs defaultValue="details">
        <Tabs.List>
          <Tabs.Tab value="details">Details</Tabs.Tab>
          <Tabs.Tab value="compliance">
            Compliance
            {(counts.regulations ?? 0) + (counts.policies ?? 0) > 0 && (
              <Badge size="xs" ml={4} variant="light" color="blue">{(counts.regulations ?? 0) + (counts.policies ?? 0)}</Badge>
            )}
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="details" pt="md">
          <Stack gap="md">
            <Paper withBorder p="lg" radius="md">
              <Stack gap="xs">
                <Group gap="xs">
                  <Text><strong>Repositories:</strong></Text>
                  {repoNames.length > 0
                    ? repoNames.map((name) => (
                        <Badge key={name} size="sm" variant="light">{name}</Badge>
                      ))
                    : <Text c="dimmed">—</Text>}
                </Group>
                <Text><strong>Default Branch:</strong> {project.default_branch}</Text>
                <Text><strong>Workflow:</strong> {project.workflow_definition_id || '—'}</Text>
                <Text><strong>AI Provider:</strong> {providerName || '—'}</Text>
                <Text><strong>Channel:</strong> {project.channel_id || '—'}</Text>
                <Text><strong>Workspace:</strong> {project.workspace_id || '—'}</Text>
              </Stack>
            </Paper>

            <Group>
              <Button onClick={startEdit}>Edit</Button>
              <Button color="red" variant="light" onClick={handleDelete} loading={deleteMut.isPending}>Delete</Button>
            </Group>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="compliance" pt="md">
          <Stack gap="md">
            {/* Quick stats */}
            <SimpleGrid cols={{ base: 2, sm: 4, lg: 8 }}>
              {complianceCards.map((card) => (
                <Paper key={card.label} withBorder p="xs" radius="md">
                  <Group gap="xs">
                    <ThemeIcon size="sm" color={card.color} variant="light">
                      <card.icon size={14} />
                    </ThemeIcon>
                    <div>
                      <Text size="lg" fw={700}>{card.count}</Text>
                      <Text size="xs" c="dimmed">{card.label}</Text>
                    </div>
                  </Group>
                </Paper>
              ))}
            </SimpleGrid>

            {/* Risk ring */}
            {Object.keys(riskDist).length > 0 && (
              <Paper withBorder p="md" radius="md">
                <Group>
                  <RingProgress
                    size={100}
                    thickness={12}
                    sections={Object.entries(riskDist).map(([level, count]) => ({
                      value: (count / totalRisk) * 100,
                      color: riskColors[level] ?? 'gray',
                      tooltip: `${level}: ${count}`,
                    }))}
                  />
                  <Stack gap={4}>
                    <Text fw={600}>Risk Distribution</Text>
                    <Group gap="xs">
                      {Object.entries(riskDist).map(([level, count]) => (
                        <Badge key={level} color={riskColors[level]} variant="light" size="sm">{level}: {count}</Badge>
                      ))}
                    </Group>
                  </Stack>
                </Group>
              </Paper>
            )}

            {/* Cascade preview */}
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
              {(['regulations', 'policies', 'procedures', 'practices'] as const).map((key) => {
                const items = cascade[key] ?? [];
                const icons: Record<string, typeof IconShieldCheck> = {
                  regulations: IconShieldCheck, policies: IconFileText,
                  procedures: IconListDetails, practices: IconTool,
                };
                const colors: Record<string, string> = {
                  regulations: 'blue', policies: 'violet', procedures: 'indigo', practices: 'teal',
                };
                const Icon = icons[key];
                return (
                  <Stack key={key} gap="xs">
                    <Group gap="xs">
                      <ThemeIcon size="sm" color={colors[key]} variant="light"><Icon size={14} /></ThemeIcon>
                      <Text fw={600} size="sm" tt="capitalize">{key}</Text>
                      <Badge size="xs" variant="light">{items.length}</Badge>
                    </Group>
                    {items.slice(0, 3).map((item) => (
                      <Card key={item.name as string} withBorder padding="xs" radius="sm">
                        <Group justify="space-between" wrap="nowrap">
                          <Text size="sm" truncate>{item.name as string}</Text>
                          {item.risk_level && (
                            <Badge size="xs" color={riskColors[(item.risk_level as string)]} variant="dot">
                              {item.risk_level as string}
                            </Badge>
                          )}
                        </Group>
                      </Card>
                    ))}
                    {items.length > 3 && <Text size="xs" c="dimmed">+{items.length - 3} more</Text>}
                  </Stack>
                );
              })}
            </SimpleGrid>

            <Button
              variant="light"
              onClick={() => void navigate(`/compliance?project=${project.project_id}`)}
            >
              View Full Compliance Dashboard
            </Button>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <Modal opened={editing} onClose={() => setEditing(false)} title="Edit Project" size="lg">
        <form onSubmit={handleSave}>
          <Stack gap="sm">
            <TextInput label="Name" {...form.getInputProps('name')} />
            <MultiSelect label="Repositories" data={repoOptions} searchable {...form.getInputProps('repo_ids')} />
            <TextInput label="Default Branch" {...form.getInputProps('default_branch')} />
            <Select label="AI Provider" data={providerOptions} searchable {...form.getInputProps('ai_provider_id')} />
            <TextInput label="Channel ID" {...form.getInputProps('channel_id')} />
            <TextInput label="Workspace ID" {...form.getInputProps('workspace_id')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
