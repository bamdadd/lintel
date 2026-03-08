import { useState } from 'react';
import {
  ActionIcon,
  SimpleGrid,
  Title,
  Stack,
  Text,
  Table,
  Loader,
  Center,
  Paper,
  Group,
  Button,
  ThemeIcon,
  List,
  Badge,
  RingProgress,
  Anchor,
} from '@mantine/core';
import {
  IconRocket,
  IconCheck,
  IconCircleDashed,
  IconX,
  IconFolder,
  IconGitBranch,
  IconCpu,
  IconBrain,
  IconTools,
  IconServer,
  IconListCheck,
  IconTimeline,
  IconActivity,
  IconShieldCheck,
  IconPlugConnected,
  IconBox,
} from '@tabler/icons-react';
import { useNavigate, Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { useMetricsOverviewMetrics } from '@/generated/api/metrics/metrics';
import { useThreadsListThreads } from '@/generated/api/threads/threads';
import { useEventsListEvents } from '@/generated/api/events/events';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { usePipelinesListPipelines } from '@/generated/api/pipelines/pipelines';
import { useWorkItemsListWorkItems } from '@/generated/api/work-items/work-items';
import { useModelsListModels } from '@/generated/api/models/models';
import { useAgentsListAgentDefinitions } from '@/generated/api/agents/agents';
import { useSkillsListSkills } from '@/generated/api/skills/skills';
import { useMcpServersListMcpServers } from '@/generated/api/mcp-servers/mcp-servers';
import { useRepositoriesListRepositories } from '@/generated/api/repositories/repositories';
import { useSandboxesListSandboxes } from '@/generated/api/sandboxes/sandboxes';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { customInstance } from '@/shared/api/client';

interface OverviewData {
  pii?: { total_detected?: number; total_anonymised?: number; total_scanned?: number };
  sandboxes?: { total?: number };
  connections?: { total?: number };
  counts?: { agent_steps?: number };
}

interface OnboardingStatus {
  has_ai_provider: boolean;
  has_repo: boolean;
  has_chat: boolean;
  is_complete: boolean;
}

function useOnboardingStatus() {
  return useQuery({
    queryKey: ['/api/v1/onboarding/status'],
    queryFn: () =>
      customInstance<{ data: OnboardingStatus; status: number }>(
        '/api/v1/onboarding/status',
        { method: 'GET' },
      ).then((r) => r.data),
  });
}

function OnboardingBanner() {
  const navigate = useNavigate();
  const { data: status, isLoading } = useOnboardingStatus();
  const [dismissed, setDismissed] = useState(false);

  if (isLoading || !status || dismissed) return null;

  const steps = [
    { label: 'AI provider configured', done: status.has_ai_provider },
    { label: 'Repository connected', done: status.has_repo },
    { label: 'Chat enabled (optional)', done: status.has_chat },
  ];

  return (
    <Paper withBorder p="lg" radius="md">
      <Group justify="space-between" align="flex-start">
        <Group align="flex-start" gap="md">
          <ThemeIcon
            size={48}
            radius="xl"
            color={status.is_complete ? 'green' : 'blue'}
            variant="light"
          >
            {status.is_complete ? <IconCheck size={24} /> : <IconRocket size={24} />}
          </ThemeIcon>
          <Stack gap="xs">
            <Title order={4}>
              {status.is_complete ? 'Workspace ready' : 'Get started with Lintel'}
            </Title>
            <Text c="dimmed" size="sm">
              {status.is_complete
                ? 'Your workspace is fully configured.'
                : 'Complete setup to start running AI workflows on your codebase.'}
            </Text>
            <List spacing={4} size="sm" mt={4}>
              {steps.map((s) => (
                <List.Item
                  key={s.label}
                  icon={
                    s.done ? (
                      <ThemeIcon color="green" size={20} radius="xl">
                        <IconCheck size={12} />
                      </ThemeIcon>
                    ) : (
                      <ThemeIcon color="gray" size={20} radius="xl" variant="light">
                        <IconCircleDashed size={12} />
                      </ThemeIcon>
                    )
                  }
                >
                  <Text size="sm" c={s.done ? 'dimmed' : undefined}>
                    {s.label}
                  </Text>
                </List.Item>
              ))}
            </List>
          </Stack>
        </Group>
        <Group gap="sm">
          {!status.is_complete && (
            <Button onClick={() => void navigate('/setup')}>
              Set up workspace
            </Button>
          )}
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={() => setDismissed(true)}
            aria-label="Dismiss onboarding banner"
          >
            <IconX size={16} />
          </ActionIcon>
        </Group>
      </Group>
    </Paper>
  );
}

const statusColors: Record<string, string> = {
  running: 'blue',
  pending: 'yellow',
  completed: 'green',
  succeeded: 'green',
  failed: 'red',
  cancelled: 'gray',
  open: 'blue',
  in_progress: 'cyan',
  done: 'green',
  blocked: 'red',
};

function StatusBreakdown({
  title,
  data,
  link,
}: {
  title: string;
  data: Record<string, number>;
  link: string;
}) {
  const entries = Object.entries(data);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return null;

  const ringData = entries.map(([status, value]) => ({
    value: (value / total) * 100,
    color: statusColors[status] ?? 'gray',
    tooltip: `${status}: ${value}`,
  }));

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="xs">
        <Text fw={600} size="sm">{title}</Text>
        <Anchor component={Link} to={link} size="xs">View all</Anchor>
      </Group>
      <Group align="center" gap="lg">
        <RingProgress size={80} thickness={8} sections={ringData} />
        <Stack gap={4}>
          {entries.map(([status, count]) => (
            <Group key={status} gap="xs">
              <Badge size="xs" color={statusColors[status] ?? 'gray'} variant="dot">
                {status}
              </Badge>
              <Text size="sm" fw={500}>{count}</Text>
            </Group>
          ))}
        </Stack>
      </Group>
    </Paper>
  );
}

interface EntityCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
  link: string;
  color: string;
}

function EntityCard({ label, value, icon, link, color }: EntityCardProps) {
  return (
    <Anchor component={Link} to={link} underline="never" style={{ color: 'inherit' }}>
      <Paper withBorder p="md" radius="md" style={{ cursor: 'pointer' }}>
        <Group justify="space-between">
          <div>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>{label}</Text>
            <Title order={3} mt={4}>{value}</Title>
          </div>
          <ThemeIcon size={40} radius="md" color={color} variant="light">
            {icon}
          </ThemeIcon>
        </Group>
      </Paper>
    </Anchor>
  );
}

const STATUS_PRIORITY: Record<string, number> = {
  in_progress: 0,
  in_review: 1,
  open: 2,
  approved: 3,
  merged: 4,
  closed: 5,
  failed: 6,
};

function getTopTasks(
  workItems: Record<string, unknown>[],
  projectMap: Map<string, string>,
  limit: number,
): Array<{ title: string; status: string; project: string; workType: string; id: string }> {
  return [...workItems]
    .sort((a, b) => {
      const pa = STATUS_PRIORITY[String(a.status)] ?? 99;
      const pb = STATUS_PRIORITY[String(b.status)] ?? 99;
      if (pa !== pb) return pa - pb;
      return (Number(a.column_position) || 0) - (Number(b.column_position) || 0);
    })
    .slice(0, limit)
    .map((wi) => ({
      id: String(wi.work_item_id ?? ''),
      title: String(wi.title ?? ''),
      status: String(wi.status ?? 'unknown'),
      project: projectMap.get(String(wi.project_id ?? '')) ?? 'Unknown',
      workType: String(wi.work_type ?? ''),
    }));
}

function countByField(items: unknown[], field: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const item of items) {
    const val = (item as Record<string, unknown>)[field];
    const key = typeof val === 'string' ? val : String(val ?? 'unknown');
    result[key] = (result[key] ?? 0) + 1;
  }
  return result;
}

export function Component() {
  const { data: overviewResp } = useMetricsOverviewMetrics();
  const { data: threadsResp, isLoading: threadsLoading } = useThreadsListThreads();
  const { data: eventsResp } = useEventsListEvents();
  const { data: projectsResp } = useProjectsListProjects();
  const { data: pipelinesResp } = usePipelinesListPipelines();
  const { data: workItemsResp } = useWorkItemsListWorkItems();
  const { data: modelsResp } = useModelsListModels();
  const { data: agentsResp } = useAgentsListAgentDefinitions();
  const { data: skillsResp } = useSkillsListSkills();
  const { data: mcpResp } = useMcpServersListMcpServers();
  const { data: reposResp } = useRepositoriesListRepositories();
  const { data: sandboxesResp } = useSandboxesListSandboxes();

  const overview = overviewResp?.data as OverviewData | undefined;
  const threads = threadsResp?.data;
  const events = (eventsResp?.data ?? []) as Record<string, unknown>[];
  const projects = (projectsResp?.data ?? []) as unknown[];
  const pipelines = (pipelinesResp?.data ?? []) as Record<string, unknown>[];
  const workItems = (workItemsResp?.data ?? []) as Record<string, unknown>[];
  const models = (modelsResp?.data ?? []) as unknown[];
  const agents = (agentsResp?.data ?? []) as unknown[];
  const skills = (skillsResp?.data ?? []) as unknown[];
  const mcpServers = (mcpResp?.data ?? []) as unknown[];
  const repos = (reposResp?.data ?? []) as unknown[];
  const sandboxes = (sandboxesResp?.data ?? []) as unknown[];

  const pipelinesByStatus = countByField(pipelines, 'status');
  const workItemsByStatus = countByField(workItems, 'status');

  const projectMap = new Map(
    projects.map((p) => {
      const proj = p as Record<string, unknown>;
      return [String(proj.project_id ?? ''), String(proj.name ?? 'Unknown')];
    }),
  );
  const topTasks = getTopTasks(workItems, projectMap, 5);

  return (
    <Stack gap="lg">
      <Title order={2}>Dashboard</Title>

      <OnboardingBanner />

      {/* Primary entity counts */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <EntityCard
          label="Projects"
          value={projects.length}
          icon={<IconFolder size={20} />}
          link="/projects"
          color="blue"
        />
        <EntityCard
          label="Pipelines"
          value={pipelines.length}
          icon={<IconTimeline size={20} />}
          link="/pipelines"
          color="violet"
        />
        <EntityCard
          label="Work Items"
          value={workItems.length}
          icon={<IconListCheck size={20} />}
          link="/boards"
          color="teal"
        />
        <EntityCard
          label="Events"
          value={events.length}
          icon={<IconActivity size={20} />}
          link="/threads"
          color="orange"
        />
      </SimpleGrid>

      {/* Infrastructure counts */}
      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }}>
        <EntityCard
          label="Models"
          value={models.length}
          icon={<IconBrain size={18} />}
          link="/models"
          color="pink"
        />
        <EntityCard
          label="Agents"
          value={agents.length}
          icon={<IconCpu size={18} />}
          link="/agents"
          color="grape"
        />
        <EntityCard
          label="Skills"
          value={skills.length}
          icon={<IconTools size={18} />}
          link="/skills"
          color="indigo"
        />
        <EntityCard
          label="MCP Servers"
          value={mcpServers.length}
          icon={<IconServer size={18} />}
          link="/mcp-servers"
          color="cyan"
        />
        <EntityCard
          label="Repositories"
          value={repos.length}
          icon={<IconGitBranch size={18} />}
          link="/repositories"
          color="lime"
        />
        <EntityCard
          label="Sandboxes"
          value={sandboxes.length}
          icon={<IconBox size={18} />}
          link="/sandboxes"
          color="yellow"
        />
      </SimpleGrid>

      {/* Status breakdowns */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {Object.keys(pipelinesByStatus).length > 0 && (
          <StatusBreakdown
            title="Pipelines by Status"
            data={pipelinesByStatus}
            link="/pipelines"
          />
        )}
        {Object.keys(workItemsByStatus).length > 0 && (
          <StatusBreakdown
            title="Work Items by Status"
            data={workItemsByStatus}
            link="/boards"
          />
        )}
        <Paper withBorder p="md" radius="md">
          <Text fw={600} size="sm" mb="xs">Security</Text>
          <Group gap="lg">
            <div>
              <Text size="xs" c="dimmed">PII Scanned</Text>
              <Text fw={500}>{overview?.pii?.total_scanned ?? 0}</Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">PII Detected</Text>
              <Text fw={500} c="orange">{overview?.pii?.total_detected ?? 0}</Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">Anonymised</Text>
              <Text fw={500} c="green">{overview?.pii?.total_anonymised ?? 0}</Text>
            </div>
          </Group>
          <Group mt="xs">
            <Badge size="sm" leftSection={<IconShieldCheck size={12} />} color="green" variant="light">
              {overview?.connections?.total ?? 0} connections
            </Badge>
            <Badge size="sm" leftSection={<IconPlugConnected size={12} />} color="blue" variant="light">
              {overview?.counts?.agent_steps ?? 0} agent steps
            </Badge>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Top Prioritised Tasks */}
      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Top Tasks</Title>
          <Anchor component={Link} to="/boards" size="sm">View all</Anchor>
        </Group>
        {topTasks.length > 0 ? (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Title</Table.Th>
                <Table.Th>Project</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {topTasks.map((task) => (
                <Table.Tr key={task.id}>
                  <Table.Td>
                    <Text size="sm" fw={500} lineClamp={1}>{task.title}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{task.project}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="xs" variant="light">{task.workType}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={task.status} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text c="dimmed" size="sm">No tasks yet. Create work items on a board to see them here.</Text>
        )}
      </Paper>

      {/* Recent Events */}
      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Recent Events</Title>
          <Anchor component={Link} to="/threads" size="sm">View all</Anchor>
        </Group>
        {events.length > 0 ? (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Event Type</Table.Th>
                <Table.Th>Stream</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {events.slice(-10).reverse().map((ev, i) => (
                <Table.Tr key={i}>
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {String(ev.event_type ?? ev.type ?? 'unknown')}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {String(ev.stream_id ?? ev.correlation_id ?? '-')}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge status={String(ev.status ?? ev.phase ?? 'recorded')} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text c="dimmed" size="sm">No events yet. Trigger a workflow to see activity here.</Text>
        )}
      </Paper>

      {/* Recent Threads */}
      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="sm">
          <Title order={4}>Recent Threads</Title>
          <Anchor component={Link} to="/threads" size="sm">View all</Anchor>
        </Group>
        {threadsLoading ? (
          <Center><Loader size="sm" /></Center>
        ) : threads && threads.length > 0 ? (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Stream ID</Table.Th>
                <Table.Th>Phase</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {threads.slice(0, 10).map((t, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{String(t.stream_id ?? '')}</Table.Td>
                  <Table.Td>{String(t.phase ?? '')}</Table.Td>
                  <Table.Td>
                    <StatusBadge status={String(t.status ?? 'unknown')} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text c="dimmed" size="sm">No threads yet.</Text>
        )}
      </Paper>
    </Stack>
  );
}
