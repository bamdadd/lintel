import { useState } from 'react';
import {
  Title, Stack, Paper, Text, Group, Badge, Loader, Center,
  SimpleGrid, Select, ThemeIcon, RingProgress, Tabs, Divider,
  Timeline, Card, Tooltip, Progress,
} from '@mantine/core';
import {
  IconShieldCheck, IconFileText, IconListDetails, IconTool,
  IconTarget, IconChartBar, IconFlask, IconBrain,
  IconArrowRight, IconAlertTriangle,
} from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useComplianceOverview } from '../api';

interface ProjectItem { project_id: string; name: string; }

const riskColors: Record<string, string> = {
  low: 'green', medium: 'yellow', high: 'orange', critical: 'red',
};

const statusColors: Record<string, string> = {
  draft: 'gray', active: 'green', under_review: 'yellow',
  deprecated: 'orange', non_compliant: 'red',
};

export function Component() {
  const { data: projectsResp, isLoading: loadingProjects } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [selectedProject, setSelectedProject] = useState<string>('');

  const { data: overviewResp, isLoading: loadingOverview } = useComplianceOverview(selectedProject);
  const overview = overviewResp?.data as Record<string, unknown> | undefined;
  const counts = (overview?.counts ?? {}) as Record<string, number>;
  const riskDist = (overview?.risk_distribution ?? {}) as Record<string, number>;
  const statusDist = (overview?.status_distribution ?? {}) as Record<string, number>;
  const cascade = (overview?.cascade ?? {}) as Record<string, Record<string, unknown>[]>;

  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const totalRisk = Object.values(riskDist).reduce((a, b) => a + b, 0) || 1;

  const statCards = [
    { label: 'Regulations', count: counts.regulations ?? 0, icon: IconShieldCheck, color: 'blue' },
    { label: 'Policies', count: counts.policies ?? 0, icon: IconFileText, color: 'violet' },
    { label: 'Procedures', count: counts.procedures ?? 0, icon: IconListDetails, color: 'indigo' },
    { label: 'Practices', count: counts.practices ?? 0, icon: IconTool, color: 'teal' },
    { label: 'Strategies', count: counts.strategies ?? 0, icon: IconTarget, color: 'cyan' },
    { label: 'KPIs', count: counts.kpis ?? 0, icon: IconChartBar, color: 'green' },
    { label: 'Experiments', count: counts.experiments ?? 0, icon: IconFlask, color: 'orange' },
    { label: 'Metrics', count: counts.metrics ?? 0, icon: IconChartBar, color: 'pink' },
    { label: 'Knowledge', count: counts.knowledge_entries ?? 0, icon: IconBrain, color: 'grape' },
  ];

  if (loadingProjects) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Compliance & Governance</Title>
        <Select
          placeholder="Select a project"
          data={projectOptions}
          value={selectedProject}
          onChange={(v) => setSelectedProject(v ?? '')}
          searchable
          clearable
          w={300}
        />
      </Group>

      {!selectedProject ? (
        <Paper withBorder p="xl" ta="center">
          <Text c="dimmed" size="lg">Select a project to view compliance governance</Text>
        </Paper>
      ) : loadingOverview ? (
        <Center py="xl"><Loader /></Center>
      ) : (
        <Tabs defaultValue="overview">
          <Tabs.List>
            <Tabs.Tab value="overview">Overview</Tabs.Tab>
            <Tabs.Tab value="cascade">Compliance Cascade</Tabs.Tab>
            <Tabs.Tab value="risk">Risk Matrix</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="overview" pt="md">
            <Stack gap="md">
              {/* Stat cards */}
              <SimpleGrid cols={{ base: 2, sm: 3, lg: 5 }}>
                {statCards.map((card) => (
                  <Paper key={card.label} withBorder p="md" radius="md">
                    <Group>
                      <ThemeIcon size="lg" radius="md" variant="light" color={card.color}>
                        <card.icon size={20} />
                      </ThemeIcon>
                      <div>
                        <Text size="xl" fw={700}>{card.count}</Text>
                        <Text size="xs" c="dimmed">{card.label}</Text>
                      </div>
                    </Group>
                  </Paper>
                ))}
              </SimpleGrid>

              {/* Risk & Status distribution */}
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Paper withBorder p="md" radius="md">
                  <Text fw={600} mb="sm">Risk Distribution</Text>
                  <Group justify="center" mb="sm">
                    <RingProgress
                      size={140}
                      thickness={16}
                      sections={Object.entries(riskDist).map(([level, count]) => ({
                        value: (count / totalRisk) * 100,
                        color: riskColors[level] ?? 'gray',
                        tooltip: `${level}: ${count}`,
                      }))}
                    />
                  </Group>
                  <Group gap="xs" justify="center">
                    {Object.entries(riskDist).map(([level, count]) => (
                      <Badge key={level} color={riskColors[level]} variant="light" size="sm">
                        {level}: {count}
                      </Badge>
                    ))}
                  </Group>
                </Paper>
                <Paper withBorder p="md" radius="md">
                  <Text fw={600} mb="sm">Status Distribution</Text>
                  <Stack gap="xs">
                    {Object.entries(statusDist).map(([status, count]) => (
                      <Group key={status} justify="space-between">
                        <Badge color={statusColors[status]} variant="light" size="sm">{status}</Badge>
                        <Text size="sm">{count}</Text>
                      </Group>
                    ))}
                  </Stack>
                </Paper>
              </SimpleGrid>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="cascade" pt="md">
            <ComplianceCascade cascade={cascade} />
          </Tabs.Panel>

          <Tabs.Panel value="risk" pt="md">
            <RiskMatrix cascade={cascade} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Compliance Cascade: Regulation → Policy → Procedure → Practice
// ---------------------------------------------------------------------------

function ComplianceCascade({ cascade }: { cascade: Record<string, Record<string, unknown>[]> }) {
  const regulations = cascade.regulations ?? [];
  const policies = cascade.policies ?? [];
  const procedures = cascade.procedures ?? [];
  const practices = cascade.practices ?? [];

  const layers = [
    { label: 'Regulations', icon: IconShieldCheck, color: 'blue', items: regulations, nameField: 'name', idField: 'regulation_id' },
    { label: 'Policies', icon: IconFileText, color: 'violet', items: policies, nameField: 'name', idField: 'policy_id', parentField: 'regulation_ids' },
    { label: 'Procedures', icon: IconListDetails, color: 'indigo', items: procedures, nameField: 'name', idField: 'procedure_id', parentField: 'policy_ids' },
    { label: 'Practices', icon: IconTool, color: 'teal', items: practices, nameField: 'name', idField: 'practice_id', parentField: 'procedure_ids' },
  ];

  return (
    <Stack gap="lg">
      <Text size="sm" c="dimmed">
        Compliance flows downward: Regulations inform Policies, which define Procedures, which become Practices.
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {layers.map((layer, i) => (
          <Stack key={layer.label} gap="xs">
            <Group gap="xs">
              <ThemeIcon size="sm" color={layer.color} variant="light">
                <layer.icon size={14} />
              </ThemeIcon>
              <Text fw={600} size="sm">{layer.label}</Text>
              <Badge size="xs" variant="light">{layer.items.length}</Badge>
            </Group>
            {i > 0 && (
              <Center>
                <IconArrowRight size={14} style={{ opacity: 0.4, transform: 'rotate(180deg)' }} />
              </Center>
            )}
            <Stack gap={4}>
              {layer.items.length === 0 ? (
                <Text size="xs" c="dimmed" fs="italic">None defined</Text>
              ) : (
                layer.items.map((item) => (
                  <Card key={item[layer.idField] as string} withBorder padding="xs" radius="sm">
                    <Group justify="space-between" wrap="nowrap">
                      <Text size="sm" truncate>{item[layer.nameField] as string}</Text>
                      <Group gap={4}>
                        {item.risk_level && (
                          <Badge
                            size="xs"
                            color={riskColors[(item.risk_level as string) ?? 'medium']}
                            variant="dot"
                          >
                            {item.risk_level as string}
                          </Badge>
                        )}
                        {item.status && (
                          <Badge
                            size="xs"
                            color={statusColors[(item.status as string) ?? 'draft']}
                            variant="light"
                          >
                            {item.status as string}
                          </Badge>
                        )}
                      </Group>
                    </Group>
                    {item.description && (
                      <Text size="xs" c="dimmed" lineClamp={2} mt={2}>{item.description as string}</Text>
                    )}
                  </Card>
                ))
              )}
            </Stack>
          </Stack>
        ))}
      </SimpleGrid>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Risk Matrix
// ---------------------------------------------------------------------------

function RiskMatrix({ cascade }: { cascade: Record<string, Record<string, unknown>[]> }) {
  const allItems = [
    ...(cascade.regulations ?? []),
    ...(cascade.policies ?? []),
    ...(cascade.procedures ?? []),
    ...(cascade.practices ?? []),
  ];

  const riskLevels = ['critical', 'high', 'medium', 'low'];
  const statuses = ['non_compliant', 'under_review', 'draft', 'active', 'deprecated'];

  // Build matrix
  const matrix: Record<string, Record<string, Record<string, unknown>[]>> = {};
  for (const risk of riskLevels) {
    matrix[risk] = {};
    for (const status of statuses) {
      matrix[risk][status] = allItems.filter(
        (item) => (item.risk_level ?? 'medium') === risk && (item.status ?? 'draft') === status,
      );
    }
  }

  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        Risk matrix showing compliance items by risk level and status.
        Items requiring attention appear in the top-left quadrant.
      </Text>
      <Paper withBorder p="md" radius="md">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ padding: 8, textAlign: 'left' }}>Risk / Status</th>
              {statuses.map((s) => (
                <th key={s} style={{ padding: 8, textAlign: 'center' }}>
                  <Badge color={statusColors[s]} variant="light" size="sm">{s.replace('_', ' ')}</Badge>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {riskLevels.map((risk) => (
              <tr key={risk}>
                <td style={{ padding: 8 }}>
                  <Badge color={riskColors[risk]} variant="filled" size="sm">{risk}</Badge>
                </td>
                {statuses.map((status) => {
                  const items = matrix[risk][status];
                  const isHot = (risk === 'critical' || risk === 'high') &&
                    (status === 'non_compliant' || status === 'under_review' || status === 'draft');
                  return (
                    <td key={status} style={{
                      padding: 8, textAlign: 'center',
                      backgroundColor: items.length > 0 && isHot ? 'var(--mantine-color-red-0)' : undefined,
                      borderRadius: 4,
                    }}>
                      {items.length > 0 ? (
                        <Tooltip label={items.map((i) => i.name as string).join(', ')}>
                          <Badge
                            size="lg"
                            color={isHot ? 'red' : 'gray'}
                            variant={isHot ? 'filled' : 'light'}
                          >
                            {items.length}
                          </Badge>
                        </Tooltip>
                      ) : (
                        <Text size="xs" c="dimmed">—</Text>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Paper>
    </Stack>
  );
}
