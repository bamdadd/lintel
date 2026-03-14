import {
  Anchor,
  Badge,
  Breadcrumbs,
  Button,
  Grid,
  Group,
  Loader,
  Paper,
  Stack,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay, IconSettings, IconTimeline } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router';

import {
  useAutomationsDeleteAutomation,
  useAutomationsGetAutomation,
  useAutomationsListAutomationRuns,
  useAutomationsTriggerAutomation,
  useAutomationsUpdateAutomation,
} from '@/generated/api/automations/automations';

import { AutomationFormModal } from '../components/AutomationFormModal';
import { NextRunsList } from '../components/NextRunsList';
import { RunTimeline } from '../components/RunTimeline';
import { RunsTable } from '../components/RunsTable';

const triggerColors: Record<string, string> = {
  cron: 'violet',
  event: 'blue',
  manual: 'gray',
};

export function Component() {
  const { automationId } = useParams<{ automationId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false);

  const { data: resp, isLoading } = useAutomationsGetAutomation(automationId ?? '', {
    query: { enabled: !!automationId },
  });
  const { data: runsResp } = useAutomationsListAutomationRuns(automationId ?? '', {
    query: { enabled: !!automationId },
  });

  const updateMut = useAutomationsUpdateAutomation();
  const deleteMut = useAutomationsDeleteAutomation();
  const triggerMut = useAutomationsTriggerAutomation();

  const auto = resp?.data as Record<string, unknown> | undefined;
  const runs = (runsResp?.data ?? []) as Array<Record<string, unknown>>;

  if (isLoading) {
    return <Loader />;
  }

  if (!auto) {
    return <Text>Automation not found</Text>;
  }

  const triggerType = String(auto.trigger_type ?? '');
  const triggerConfig = (auto.trigger_config ?? {}) as Record<string, unknown>;
  const enabled = Boolean(auto.enabled);

  const handleTrigger = () => {
    triggerMut.mutate(
      { automationId: automationId! },
      {
        onSuccess: () => {
          notifications.show({ title: 'Triggered', message: 'Automation fired', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
        },
      },
    );
  };

  const handleUpdate = (values: Record<string, unknown>) => {
    updateMut.mutate(
      { automationId: automationId!, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Automation updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
          closeEdit();
        },
      },
    );
  };

  const handleDelete = () => {
    const confirmed = window.confirm(`Are you sure you want to delete "${String(auto.name)}"? This cannot be undone.`);
    if (!confirmed) return;
    deleteMut.mutate(
      { automationId: automationId! },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Automation deleted', color: 'green' });
          navigate('/automations');
        },
      },
    );
  };

  const editInitialValues = {
    name: String(auto.name ?? ''),
    project_id: String(auto.project_id ?? ''),
    workflow_definition_id: String(auto.workflow_definition_id ?? ''),
    trigger_type: triggerType,
    schedule: String(triggerConfig.schedule ?? ''),
    timezone: String(triggerConfig.timezone ?? 'UTC'),
    event_types: Array.isArray(triggerConfig.event_types) ? triggerConfig.event_types.map(String) : [],
    concurrency_policy: String(auto.concurrency_policy ?? 'queue'),
    enabled,
  };

  const passedCount = runs.filter((r) => r.status === 'completed' || r.status === 'succeeded').length;
  const failedCount = runs.filter((r) => r.status === 'failed').length;
  const skippedCount = runs.filter((r) => r.status === 'skipped' || r.status === 'cancelled').length;

  return (
    <Stack gap="md">
      <Breadcrumbs>
        <Anchor onClick={() => navigate('/automations')}>Automations</Anchor>
        <Text>{String(auto.name)}</Text>
      </Breadcrumbs>

      <Group justify="space-between">
        <Group gap="sm">
          <Title order={2}>{String(auto.name)}</Title>
          <Badge color={enabled ? 'green' : 'gray'}>{enabled ? 'Enabled' : 'Disabled'}</Badge>
          <Badge color={triggerColors[triggerType] ?? 'gray'}>{triggerType}</Badge>
        </Group>
        <Group gap="xs">
          <Button variant="default" leftSection={<IconPlayerPlay size={16} />} onClick={handleTrigger}>
            Trigger Now
          </Button>
          <Button variant="default" leftSection={<IconSettings size={16} />} onClick={openEdit}>
            Edit
          </Button>
        </Group>
      </Group>

      <Tabs defaultValue="overview">
        <Tabs.List>
          <Tabs.Tab value="overview" leftSection={<IconTimeline size={14} />}>Overview</Tabs.Tab>
          <Tabs.Tab value="runs">Runs</Tabs.Tab>
          <Tabs.Tab value="settings" leftSection={<IconSettings size={14} />}>Settings</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          <Grid>
            <Grid.Col span={6}>
              <Paper p="md" radius="md" withBorder>
                <Text size="sm" fw={500} mb="sm">Configuration</Text>
                <Stack gap={4}>
                  <Group><Text size="xs" c="dimmed" w={100}>Project</Text><Text size="xs">{String(auto.project_id)}</Text></Group>
                  <Group><Text size="xs" c="dimmed" w={100}>Workflow</Text><Text size="xs">{String(auto.workflow_definition_id)}</Text></Group>
                  {triggerType === 'cron' && (
                    <>
                      <Group><Text size="xs" c="dimmed" w={100}>Schedule</Text><Text size="xs" ff="monospace">{String(triggerConfig.schedule)}</Text></Group>
                      <Group><Text size="xs" c="dimmed" w={100}>Timezone</Text><Text size="xs">{String(triggerConfig.timezone ?? 'UTC')}</Text></Group>
                    </>
                  )}
                  {triggerType === 'event' && (
                    <Group><Text size="xs" c="dimmed" w={100}>Events</Text><Text size="xs">{(triggerConfig.event_types as string[])?.join(', ')}</Text></Group>
                  )}
                  <Group><Text size="xs" c="dimmed" w={100}>Concurrency</Text><Text size="xs">{String(auto.concurrency_policy)}</Text></Group>
                  <Group><Text size="xs" c="dimmed" w={100}>Chain Depth</Text><Text size="xs">{String(auto.max_chain_depth ?? 3)}</Text></Group>
                </Stack>
              </Paper>
            </Grid.Col>
            <Grid.Col span={6}>
              <Stack gap="md">
                {triggerType === 'cron' && (
                  <Paper p="md" radius="md" withBorder>
                    <Text size="sm" fw={500} mb="sm">Next 5 Runs</Text>
                    <NextRunsList schedule={String(triggerConfig.schedule)} timezone={String(triggerConfig.timezone ?? 'UTC')} />
                  </Paper>
                )}
                {triggerType !== 'cron' && (
                  <Paper p="md" radius="md" withBorder>
                    <Text size="sm" fw={500} mb="sm">Trigger</Text>
                    <Text size="xs" c="dimmed">Triggered on demand</Text>
                  </Paper>
                )}
                <Paper p="md" radius="md" withBorder>
                  <Text size="sm" fw={500} mb="sm">Quick Stats</Text>
                  <Group grow>
                    <Stack align="center" gap={0}><Text size="lg" fw={600} c="green">{passedCount}</Text><Text size="xs" c="dimmed">Passed</Text></Stack>
                    <Stack align="center" gap={0}><Text size="lg" fw={600} c="red">{failedCount}</Text><Text size="xs" c="dimmed">Failed</Text></Stack>
                    <Stack align="center" gap={0}><Text size="lg" fw={600} c="dimmed">{skippedCount}</Text><Text size="xs" c="dimmed">Skipped</Text></Stack>
                  </Group>
                </Paper>
              </Stack>
            </Grid.Col>
          </Grid>
          <RunTimeline runs={runs.map((r) => ({ status: String(r.status), created_at: String(r.created_at) }))} />
        </Tabs.Panel>

        <Tabs.Panel value="runs" pt="md">
          <RunsTable runs={runs.map((r) => ({
            run_id: String(r.run_id ?? ''),
            status: String(r.status ?? ''),
            created_at: String(r.created_at ?? ''),
            completed_at: r.completed_at ? String(r.completed_at) : undefined,
            stages: Array.isArray(r.stages) ? r.stages.map((s: Record<string, unknown>) => ({
              name: String(s.name ?? ''),
              status: String(s.status ?? ''),
              duration_ms: s.duration_ms != null ? Number(s.duration_ms) : undefined,
            })) : [],
          }))} />
        </Tabs.Panel>

        <Tabs.Panel value="settings" pt="md">
          <Stack gap="md">
            <Paper p="md" radius="md" withBorder>
              <Text size="sm" fw={500} mb="md">Edit Configuration</Text>
              <Text size="xs" c="dimmed">Use the Edit button above to modify this automation, or delete it below.</Text>
            </Paper>
            <Button color="red" variant="outline" onClick={handleDelete}>
              Delete Automation
            </Button>
          </Stack>
        </Tabs.Panel>
      </Tabs>

      <AutomationFormModal
        opened={editOpened}
        onClose={closeEdit}
        onSubmit={handleUpdate}
        initialValues={editInitialValues}
        editMode
        loading={updateMut.isPending}
      />
    </Stack>
  );
}
