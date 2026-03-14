# Automations UI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full UI for managing automations — card grid list, tabbed detail page with run history and timeline, and create/edit modal.

**Architecture:** Orval-generated React Query hooks for data fetching, Mantine v8 components, lazy-loaded routes. Card grid for list, tabbed detail with Overview (config + next runs + timeline), Runs (expandable table), and Settings (edit form). New "Scheduling" sidebar section.

**Tech Stack:** React 19, TypeScript, Mantine v8, React Router v7, React Query v5 (Orval), Recharts, cronstrue, cron-parser, @tabler/icons-react

---

## File Structure

| File | Responsibility |
|------|---------------|
| Create: `ui/src/features/automations/pages/AutomationListPage.tsx` | Card grid listing all automations |
| Create: `ui/src/features/automations/pages/AutomationDetailPage.tsx` | Tabbed detail: Overview, Runs, Settings |
| Create: `ui/src/features/automations/components/AutomationCard.tsx` | Single automation card with status border + toggle |
| Create: `ui/src/features/automations/components/AutomationFormModal.tsx` | Create/edit modal with dynamic trigger config |
| Create: `ui/src/features/automations/components/RunsTable.tsx` | Expandable runs table with inline stage view |
| Create: `ui/src/features/automations/components/RunTimeline.tsx` | 7-day bar chart of run results |
| Create: `ui/src/features/automations/components/NextRunsList.tsx` | Next 5 cron fire times |
| Modify: `ui/src/app/routes.tsx` | Add automations routes |
| Modify: `ui/src/shared/layout/AppLayout.tsx` | Add "Scheduling" nav section |

---

## Chunk 1: Setup & Dependencies

### Task 1: Install client-side dependencies

**Files:**
- Modify: `ui/package.json`

- [ ] **Step 1: Install cronstrue and cron-parser**

```bash
cd ui && npm install cronstrue cron-parser
```

- [ ] **Step 2: Verify installation**

```bash
cd ui && node -e "const c = require('cronstrue'); console.log(c.toString('0 2 * * *'))"
```

Expected: `At 02:00 AM`

- [ ] **Step 3: Commit**

```bash
git add ui/package.json ui/package-lock.json
git commit -m "feat(ui): add cronstrue and cron-parser dependencies"
```

### Task 2: Generate Orval hooks

**Files:**
- Modify: `ui/src/generated/` (auto-generated)

The backend must be running so openapi.json is available.

- [ ] **Step 1: Generate OpenAPI spec from running backend**

```bash
cd ui && curl -s http://localhost:8000/openapi.json -o ../openapi.json
```

- [ ] **Step 2: Run Orval to generate hooks**

```bash
cd ui && npm run generate:api
```

- [ ] **Step 3: Verify automations hooks were generated**

```bash
ls ui/src/generated/api/automations/
```

Expected: `automations.ts` file containing `useAutomationsListAutomations`, `useAutomationsCreateAutomation`, etc.

- [ ] **Step 4: Commit**

```bash
git add ui/src/generated/ ui/openapi.json
git commit -m "feat(ui): generate orval hooks for automations API"
```

Note: if `openapi.json` is gitignored, only commit `ui/src/generated/`.

### Task 3: Add routes and sidebar navigation

**Files:**
- Modify: `ui/src/app/routes.tsx`
- Modify: `ui/src/shared/layout/AppLayout.tsx`

- [ ] **Step 1: Add routes**

In `ui/src/app/routes.tsx`, add these two entries inside the `children` array of the root layout route, near other feature routes:

```typescript
{
  path: 'automations',
  lazy: () => import('@/features/automations/pages/AutomationListPage'),
},
{
  path: 'automations/:automationId',
  lazy: () => import('@/features/automations/pages/AutomationDetailPage'),
},
```

- [ ] **Step 2: Add sidebar section**

In `ui/src/shared/layout/AppLayout.tsx`, add a new section to the `navSections` array. Insert it after the "Development" section and before "AI & Agents":

```typescript
{
  label: 'Scheduling',
  items: [
    { label: 'Automations', path: '/automations', icon: IconCalendarEvent },
  ],
},
```

Add the icon import at the top:

```typescript
import { IconCalendarEvent } from '@tabler/icons-react';
```

- [ ] **Step 3: Create placeholder pages so routes don't crash**

Create `ui/src/features/automations/pages/AutomationListPage.tsx`:

```tsx
import { Stack, Title } from '@mantine/core';

export function Component() {
  return (
    <Stack gap="md">
      <Title order={2}>Automations</Title>
    </Stack>
  );
}
```

Create `ui/src/features/automations/pages/AutomationDetailPage.tsx`:

```tsx
import { Stack, Title } from '@mantine/core';

export function Component() {
  return (
    <Stack gap="md">
      <Title order={2}>Automation Detail</Title>
    </Stack>
  );
}
```

- [ ] **Step 4: Verify in browser**

Navigate to `http://localhost:5173/automations` — should see the placeholder page. Sidebar should show "Scheduling" section with "Automations" link.

- [ ] **Step 5: Commit**

```bash
git add ui/src/app/routes.tsx ui/src/shared/layout/AppLayout.tsx ui/src/features/automations/
git commit -m "feat(ui): add automations routes and sidebar navigation"
```

---

## Chunk 2: List Page Components

### Task 4: AutomationCard component

**Files:**
- Create: `ui/src/features/automations/components/AutomationCard.tsx`

- [ ] **Step 1: Create the AutomationCard component**

This card displays one automation in the grid. It shows name, project, trigger type badge, trigger config preview, last run status, and an enable/disable toggle. Left border is color-coded by status.

```tsx
import { ActionIcon, Badge, Group, Paper, Stack, Switch, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';

import {
  useAutomationsTriggerAutomation,
  useAutomationsUpdateAutomation,
} from '@/generated/api/automations/automations';

interface AutomationCardProps {
  automation: {
    automation_id: string;
    name: string;
    project_id: string;
    trigger_type: string;
    trigger_config: Record<string, unknown>;
    concurrency_policy: string;
    enabled: boolean;
  };
  lastRunStatus?: 'completed' | 'failed' | null;
  lastRunTime?: string | null;
}

const triggerColors: Record<string, string> = {
  cron: 'violet',
  event: 'blue',
  manual: 'gray',
};

function getBorderColor(enabled: boolean, lastRunStatus?: string | null): string {
  if (!enabled) return 'var(--mantine-color-dark-4)';
  if (lastRunStatus === 'completed') return 'var(--mantine-color-green-6)';
  if (lastRunStatus === 'failed') return 'var(--mantine-color-red-6)';
  return 'var(--mantine-color-dark-4)';
}

function getTriggerPreview(triggerType: string, config: Record<string, unknown>): string {
  if (triggerType === 'cron') return String(config.schedule ?? '');
  if (triggerType === 'event') {
    const types = config.event_types;
    if (Array.isArray(types)) return types.join(', ');
  }
  return 'On demand';
}

export function AutomationCard({ automation, lastRunStatus, lastRunTime }: AutomationCardProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const updateMut = useAutomationsUpdateAutomation();
  const triggerMut = useAutomationsTriggerAutomation();

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    updateMut.mutate(
      { automationId: automation.automation_id, data: { enabled: !automation.enabled } },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
        },
      },
    );
  };

  const handleTrigger = (e: React.MouseEvent) => {
    e.stopPropagation();
    triggerMut.mutate(
      { automationId: automation.automation_id },
      {
        onSuccess: () => {
          notifications.show({ title: 'Triggered', message: `${automation.name} fired`, color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to trigger automation', color: 'red' });
        },
      },
    );
  };

  return (
    <Paper
      p="md"
      radius="md"
      withBorder
      style={{
        borderLeftWidth: 3,
        borderLeftColor: getBorderColor(automation.enabled, lastRunStatus),
        cursor: 'pointer',
        opacity: automation.enabled ? 1 : 0.6,
      }}
      onClick={() => navigate(`/automations/${automation.automation_id}`)}
    >
      <Group justify="space-between" align="start" mb="xs">
        <Text fw={500} size="sm">{automation.name}</Text>
        <Group gap="xs">
          {automation.trigger_type === 'manual' && (
            <ActionIcon size="sm" variant="subtle" onClick={handleTrigger} title="Trigger now">
              <IconPlayerPlay size={14} />
            </ActionIcon>
          )}
          <Switch
            size="xs"
            checked={automation.enabled}
            onClick={handleToggle}
            onChange={() => {}}
          />
        </Group>
      </Group>
      <Text size="xs" c="dimmed" mb="xs">{automation.project_id}</Text>
      <Group gap="xs" mb="xs">
        <Badge size="xs" color={triggerColors[automation.trigger_type] ?? 'gray'}>
          {automation.trigger_type}
        </Badge>
        <Text size="xs" c="dimmed" ff="monospace">
          {getTriggerPreview(automation.trigger_type, automation.trigger_config)}
        </Text>
      </Group>
      {lastRunTime ? (
        <Text size="xs" c={lastRunStatus === 'failed' ? 'red' : 'green'}>
          Last run: {lastRunTime} {lastRunStatus === 'completed' ? '✓' : '✗'}
        </Text>
      ) : (
        <Text size="xs" c="dimmed">No runs yet</Text>
      )}
    </Paper>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/automations/components/AutomationCard.tsx
git commit -m "feat(ui): add AutomationCard component"
```

### Task 5: AutomationFormModal component

**Files:**
- Create: `ui/src/features/automations/components/AutomationFormModal.tsx`

- [ ] **Step 1: Create the form modal**

Dynamic form that shows different trigger config fields based on trigger type selection. Used for both create and edit (edit mode disables trigger_type).

```tsx
import {
  Button,
  Group,
  Modal,
  MultiSelect,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import cronstrue from 'cronstrue';
import { useEffect, useState } from 'react';

import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';

interface AutomationFormValues {
  name: string;
  project_id: string;
  workflow_definition_id: string;
  trigger_type: string;
  schedule: string;
  timezone: string;
  event_types: string[];
  concurrency_policy: string;
  enabled: boolean;
}

interface AutomationFormModalProps {
  opened: boolean;
  onClose: () => void;
  onSubmit: (values: {
    name: string;
    project_id: string;
    workflow_definition_id: string;
    trigger_type: string;
    trigger_config: Record<string, unknown>;
    concurrency_policy: string;
    enabled: boolean;
  }) => void;
  initialValues?: Partial<AutomationFormValues>;
  editMode?: boolean;
  loading?: boolean;
}

const CONCURRENCY_OPTIONS = [
  { value: 'queue', label: 'Queue — one at a time, FIFO' },
  { value: 'allow', label: 'Allow — run all simultaneously' },
  { value: 'skip', label: 'Skip — drop if already running' },
  { value: 'cancel', label: 'Cancel — cancel in-flight, start new' },
];

const KNOWN_EVENT_TYPES = [
  'PipelineRunCompleted',
  'PipelineRunFailed',
  'WorkItemCreated',
  'WorkItemUpdated',
  'AutomationFired',
];

function getCronDescription(expr: string): string | null {
  try {
    return cronstrue.toString(expr);
  } catch {
    return null;
  }
}

export function AutomationFormModal({
  opened,
  onClose,
  onSubmit,
  initialValues,
  editMode = false,
  loading = false,
}: AutomationFormModalProps) {
  const form = useForm<AutomationFormValues>({
    initialValues: {
      name: '',
      project_id: '',
      workflow_definition_id: '',
      trigger_type: 'cron',
      schedule: '',
      timezone: 'UTC',
      event_types: [],
      concurrency_policy: 'queue',
      enabled: true,
      ...initialValues,
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Name is required'),
      project_id: (v) => (v ? null : 'Project is required'),
      workflow_definition_id: (v) => (v ? null : 'Workflow is required'),
      schedule: (v, values) =>
        values.trigger_type === 'cron' && !v.trim() ? 'Cron expression is required' : null,
      event_types: (v, values) =>
        values.trigger_type === 'event' && v.length === 0 ? 'Select at least one event type' : null,
    },
  });

  const [cronDesc, setCronDesc] = useState<string | null>(null);

  useEffect(() => {
    if (form.values.trigger_type === 'cron' && form.values.schedule) {
      setCronDesc(getCronDescription(form.values.schedule));
    } else {
      setCronDesc(null);
    }
  }, [form.values.schedule, form.values.trigger_type]);

  useEffect(() => {
    if (initialValues && opened) {
      form.setValues({
        name: '',
        project_id: '',
        workflow_definition_id: '',
        trigger_type: 'cron',
        schedule: '',
        timezone: 'UTC',
        event_types: [],
        concurrency_policy: 'queue',
        enabled: true,
        ...initialValues,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const { data: projectsResp } = useProjectsListProjects();
  const { data: workflowsResp } = useWorkflowDefinitionsListWorkflowDefinitions();

  const projectOptions = (projectsResp?.data ?? []).map((p: Record<string, unknown>) => ({
    value: String(p.project_id ?? ''),
    label: String(p.name ?? p.project_id ?? ''),
  }));

  const workflowOptions = (workflowsResp?.data ?? []).map((w: Record<string, unknown>) => ({
    value: String(w.workflow_id ?? ''),
    label: String(w.name ?? w.workflow_id ?? ''),
  }));

  const handleSubmit = form.onSubmit((values) => {
    let trigger_config: Record<string, unknown> = {};
    if (values.trigger_type === 'cron') {
      trigger_config = { schedule: values.schedule, timezone: values.timezone };
    } else if (values.trigger_type === 'event') {
      trigger_config = { event_types: values.event_types };
    }
    onSubmit({
      name: values.name,
      project_id: values.project_id,
      workflow_definition_id: values.workflow_definition_id,
      trigger_type: values.trigger_type,
      trigger_config,
      concurrency_policy: values.concurrency_policy,
      enabled: values.enabled,
    });
  });

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={editMode ? 'Edit Automation' : 'Create Automation'}
      size="md"
    >
      <form onSubmit={handleSubmit}>
        <Stack gap="sm">
          <TextInput label="Name" required {...form.getInputProps('name')} />

          <Group grow>
            <Select
              label="Project"
              required
              data={projectOptions}
              searchable
              {...form.getInputProps('project_id')}
            />
            <Select
              label="Workflow"
              required
              data={workflowOptions}
              searchable
              {...form.getInputProps('workflow_definition_id')}
            />
          </Group>

          <div>
            <Text size="sm" fw={500} mb={4}>Trigger Type {!editMode && <span style={{ color: 'var(--mantine-color-red-6)' }}>*</span>}</Text>
            <SegmentedControl
              fullWidth
              data={[
                { value: 'cron', label: 'Cron' },
                { value: 'event', label: 'Event' },
                { value: 'manual', label: 'Manual' },
              ]}
              disabled={editMode}
              {...form.getInputProps('trigger_type')}
            />
          </div>

          {form.values.trigger_type === 'cron' && (
            <Stack gap="xs">
              <TextInput
                label="Cron Expression"
                required
                placeholder="0 2 * * *"
                styles={{ input: { fontFamily: 'monospace' } }}
                {...form.getInputProps('schedule')}
              />
              {cronDesc && (
                <Text size="xs" c="green">{cronDesc}</Text>
              )}
              <Select
                label="Timezone"
                data={['UTC', 'US/Eastern', 'US/Pacific', 'Europe/London', 'Europe/Berlin', 'Asia/Tokyo']}
                {...form.getInputProps('timezone')}
              />
            </Stack>
          )}

          {form.values.trigger_type === 'event' && (
            <MultiSelect
              label="Event Types"
              required
              data={KNOWN_EVENT_TYPES}
              searchable
              {...form.getInputProps('event_types')}
            />
          )}

          <Select
            label="Concurrency Policy"
            data={CONCURRENCY_OPTIONS}
            {...form.getInputProps('concurrency_policy')}
          />

          <Group justify="space-between">
            <Text size="sm">Start enabled</Text>
            <Switch {...form.getInputProps('enabled', { type: 'checkbox' })} />
          </Group>

          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={loading}>
              {editMode ? 'Save' : 'Create'}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/automations/components/AutomationFormModal.tsx
git commit -m "feat(ui): add AutomationFormModal with dynamic trigger config"
```

### Task 6: AutomationListPage

**Files:**
- Modify: `ui/src/features/automations/pages/AutomationListPage.tsx`

- [ ] **Step 1: Implement the list page**

Replace the placeholder with the full card grid implementation:

```tsx
import { Button, Group, SimpleGrid, Stack, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';

import { EmptyState } from '@/shared/components/EmptyState';

import {
  useAutomationsCreateAutomation,
  useAutomationsListAutomations,
} from '@/generated/api/automations/automations';

import { AutomationCard } from '../components/AutomationCard';
import { AutomationFormModal } from '../components/AutomationFormModal';

export function Component() {
  const { data: resp, isLoading } = useAutomationsListAutomations();
  const createMut = useAutomationsCreateAutomation();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const automations = resp?.data ?? [];

  const handleCreate = (values: Parameters<typeof createMut.mutate>[0]['data']) => {
    createMut.mutate(
      { data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Automation created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create automation', color: 'red' });
        },
      },
    );
  };

  if (isLoading) {
    return (
      <Stack gap="md">
        <Title order={2}>Automations</Title>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Automations</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>
          Create Automation
        </Button>
      </Group>

      {automations.length === 0 ? (
        <EmptyState
          title="No automations"
          description="Create automations to run workflows on a schedule, in response to events, or on demand."
          actionLabel="Create Automation"
          onAction={open}
        />
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          {automations.map((auto: Record<string, unknown>) => (
            <AutomationCard
              key={String(auto.automation_id)}
              automation={{
                automation_id: String(auto.automation_id ?? ''),
                name: String(auto.name ?? ''),
                project_id: String(auto.project_id ?? ''),
                trigger_type: String(auto.trigger_type ?? ''),
                trigger_config: (auto.trigger_config ?? {}) as Record<string, unknown>,
                concurrency_policy: String(auto.concurrency_policy ?? ''),
                enabled: Boolean(auto.enabled),
              }}
            />
          ))}
        </SimpleGrid>
      )}

      <AutomationFormModal
        opened={opened}
        onClose={close}
        onSubmit={handleCreate}
        loading={createMut.isPending}
      />
    </Stack>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:5173/automations` — should see empty state or card grid if automations exist.

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/automations/pages/AutomationListPage.tsx
git commit -m "feat(ui): implement AutomationListPage with card grid"
```

---

## Chunk 3: Detail Page Components

### Task 7: NextRunsList component

**Files:**
- Create: `ui/src/features/automations/components/NextRunsList.tsx`

- [ ] **Step 1: Create the component**

Computes and displays the next 5 cron fire times client-side.

```tsx
import { Stack, Text } from '@mantine/core';
import { parseExpression } from 'cron-parser';

interface NextRunsListProps {
  schedule: string;
  timezone?: string;
  count?: number;
}

export function NextRunsList({ schedule, timezone = 'UTC', count = 5 }: NextRunsListProps) {
  let dates: Date[] = [];
  try {
    const interval = parseExpression(schedule, { tz: timezone });
    for (let i = 0; i < count; i++) {
      dates.push(interval.next().toDate());
    }
  } catch {
    return <Text size="xs" c="red">Invalid cron expression</Text>;
  }

  return (
    <Stack gap={4}>
      {dates.map((d, i) => (
        <Text key={i} size="xs" ff="monospace" c={i < 2 ? undefined : 'dimmed'}>
          {d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC')}
        </Text>
      ))}
    </Stack>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/automations/components/NextRunsList.tsx
git commit -m "feat(ui): add NextRunsList component"
```

### Task 8: RunTimeline component

**Files:**
- Create: `ui/src/features/automations/components/RunTimeline.tsx`

- [ ] **Step 1: Create the component**

7-day bar chart showing run results color-coded by status.

```tsx
import { Paper, Text } from '@mantine/core';
import { BarChart } from '@mantine/charts';

interface RunTimelineProps {
  runs: Array<{
    status: string;
    created_at: string;
  }>;
}

function getLast7Days(): string[] {
  const days: string[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toLocaleDateString('en-US', { weekday: 'short' }));
  }
  return days;
}

function bucketRuns(runs: RunTimelineProps['runs']): Array<{ day: string; passed: number; failed: number }> {
  const days = getLast7Days();
  const now = new Date();
  const buckets: Record<string, { passed: number; failed: number }> = {};
  for (const day of days) {
    buckets[day] = { passed: 0, failed: 0 };
  }

  for (const run of runs) {
    const runDate = new Date(run.created_at);
    const diffDays = Math.floor((now.getTime() - runDate.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays >= 0 && diffDays < 7) {
      const dayLabel = runDate.toLocaleDateString('en-US', { weekday: 'short' });
      if (buckets[dayLabel]) {
        if (run.status === 'completed' || run.status === 'succeeded') {
          buckets[dayLabel].passed++;
        } else if (run.status === 'failed') {
          buckets[dayLabel].failed++;
        }
      }
    }
  }

  return days.map((day) => ({ day, ...buckets[day] }));
}

export function RunTimeline({ runs }: RunTimelineProps) {
  const data = bucketRuns(runs);
  const hasData = data.some((d) => d.passed > 0 || d.failed > 0);

  if (!hasData) {
    return (
      <Paper p="md" radius="md" withBorder>
        <Text size="sm" fw={500} mb="xs">Run Timeline (7 days)</Text>
        <Text size="xs" c="dimmed">No runs in the last 7 days</Text>
      </Paper>
    );
  }

  return (
    <Paper p="md" radius="md" withBorder>
      <Text size="sm" fw={500} mb="xs">Run Timeline (7 days)</Text>
      <BarChart
        h={120}
        data={data}
        dataKey="day"
        type="stacked"
        series={[
          { name: 'passed', color: 'green' },
          { name: 'failed', color: 'red' },
        ]}
        withTooltip
        withLegend={false}
      />
    </Paper>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/automations/components/RunTimeline.tsx
git commit -m "feat(ui): add RunTimeline bar chart component"
```

### Task 9: RunsTable component

**Files:**
- Create: `ui/src/features/automations/components/RunsTable.tsx`

- [ ] **Step 1: Create the expandable runs table**

Table rows expand to show pipeline stages inline.

```tsx
import { Badge, Group, Paper, Stack, Table, Text, UnstyledButton } from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';

import { StatusBadge } from '@/shared/components/StatusBadge';

interface PipelineRun {
  run_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  stages?: Array<{
    name: string;
    status: string;
    duration_ms?: number;
  }>;
}

interface RunsTableProps {
  runs: PipelineRun[];
}

function formatDuration(startStr: string, endStr?: string): string {
  if (!endStr) return '—';
  const start = new Date(startStr).getTime();
  const end = new Date(endStr).getTime();
  const seconds = Math.floor((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m ${secs}s`;
}

function formatTimeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <Table.Tr
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <Table.Td w={30}>
          {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </Table.Td>
        <Table.Td>
          <Text size="xs" ff="monospace">{run.run_id.slice(0, 12)}</Text>
        </Table.Td>
        <Table.Td><StatusBadge status={run.status} /></Table.Td>
        <Table.Td><Text size="xs">{formatTimeAgo(run.created_at)}</Text></Table.Td>
        <Table.Td><Text size="xs">{formatDuration(run.created_at, run.completed_at)}</Text></Table.Td>
      </Table.Tr>
      {expanded && (
        <Table.Tr>
          <Table.Td colSpan={5} style={{ background: 'var(--mantine-color-dark-7)' }}>
            <Stack gap="xs" p="xs">
              <Text size="xs" c="dimmed">Pipeline Stages</Text>
              <Group gap="xs">
                {(run.stages ?? []).map((stage) => (
                  <Paper key={stage.name} p="xs" radius="sm" withBorder style={{ flex: 1 }}>
                    <Text size="xs" c="dimmed">{stage.name}</Text>
                    <StatusBadge status={stage.status} />
                    {stage.duration_ms != null && (
                      <Text size="xs" c="dimmed" mt={2}>
                        {Math.round(stage.duration_ms / 1000)}s
                      </Text>
                    )}
                  </Paper>
                ))}
              </Group>
              <Group justify="flex-end">
                <UnstyledButton onClick={() => navigate(`/pipelines/${run.run_id}`)}>
                  <Text size="xs" c="blue">View full pipeline →</Text>
                </UnstyledButton>
              </Group>
            </Stack>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

export function RunsTable({ runs }: RunsTableProps) {
  if (runs.length === 0) {
    return <Text size="sm" c="dimmed">No runs yet</Text>;
  }

  return (
    <Table highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={30} />
          <Table.Th>Run ID</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>Started</Table.Th>
          <Table.Th>Duration</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {runs.map((run) => (
          <RunRow key={run.run_id} run={run} />
        ))}
      </Table.Tbody>
    </Table>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/automations/components/RunsTable.tsx
git commit -m "feat(ui): add RunsTable with expandable stage view"
```

---

## Chunk 4: Detail Page

### Task 10: AutomationDetailPage

**Files:**
- Modify: `ui/src/features/automations/pages/AutomationDetailPage.tsx`

- [ ] **Step 1: Implement the full detail page**

Replace the placeholder with the tabbed detail view:

```tsx
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
import { modals } from '@mantine/modals';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay, IconSettings, IconTimeline } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router';

import { StatusBadge } from '@/shared/components/StatusBadge';

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
    modals.openConfirmModal({
      title: 'Delete Automation',
      children: <Text size="sm">Are you sure you want to delete "{String(auto.name)}"? This cannot be undone.</Text>,
      labels: { confirm: 'Delete', cancel: 'Cancel' },
      confirmProps: { color: 'red' },
      onConfirm: () => {
        deleteMut.mutate(
          { automationId: automationId! },
          {
            onSuccess: () => {
              notifications.show({ title: 'Deleted', message: 'Automation deleted', color: 'green' });
              navigate('/automations');
            },
          },
        );
      },
    });
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
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:5173/automations/<some-id>` — should show the tabbed detail page.

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/automations/pages/AutomationDetailPage.tsx
git commit -m "feat(ui): implement AutomationDetailPage with tabs"
```

---

## Chunk 5: Final Validation

### Task 11: Build and lint check

- [ ] **Step 1: Run TypeScript build**

```bash
cd ui && npx tsc --noEmit
```

Fix any type errors.

- [ ] **Step 2: Run lint**

```bash
cd ui && npm run lint
```

Fix any lint errors.

- [ ] **Step 3: Run dev build**

```bash
cd ui && npm run build
```

Verify build succeeds with no errors.

- [ ] **Step 4: Manual browser test**

1. Navigate to `/automations` — verify card grid or empty state
2. Click "Create Automation" — verify form modal opens with dynamic trigger fields
3. Create a cron automation — verify cron expression preview works
4. Click the card — verify detail page with Overview tab
5. Check Runs tab — verify expandable rows (may be empty)
6. Click "Trigger Now" — verify notification
7. Toggle enable/disable on card — verify switch works

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix(ui): resolve build and lint issues in automations UI"
```
