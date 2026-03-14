import { useState } from 'react';
import {
  Title, Stack, Table, Loader, Center, Badge, Text, Select, Group,
  Collapse, Paper, ActionIcon, Pagination, Anchor,
} from '@mantine/core';
import { IconChevronDown, IconChevronRight, IconExternalLink } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { useEventsListEventTypes } from '@/generated/api/events/events';
import { customInstance } from '@/shared/api/client';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';

interface EventItem {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
  actor_id: string;
  actor_type: string;
  correlation_id: string | null;
}

interface PaginatedEvents {
  items: EventItem[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 50;

const eventColor: Record<string, string> = {
  Created: 'green',
  Registered: 'green',
  Stored: 'green',
  Updated: 'blue',
  Removed: 'red',
  Deleted: 'red',
  Completed: 'teal',
  Failed: 'orange',
  Started: 'cyan',
  Approved: 'teal',
  Rejected: 'orange',
  Cancelled: 'yellow',
  Granted: 'lime',
  Revoked: 'red',
};

/** Map event type prefix to a UI route with :id placeholder */
const RESOURCE_ROUTES: Record<string, string> = {
  Project: '/projects/:id',
  WorkItem: '/work-items',
  Pipeline: '/pipelines/runs/:id',
  PipelineRun: '/pipelines/runs/:id',
  PipelineStage: '/pipelines/runs/:id',
  StageReport: '/pipelines/runs/:id',
  Conversation: '/chat/:id',
  Repository: '/repositories/:id',
  Sandbox: '/sandboxes/:id',
  AgentDefinition: '/agents/:id',
  Credential: '/credentials',
  Trigger: '/triggers',
  Variable: '/variables',
  Environment: '/environments',
  Policy: '/policies',
  Team: '/teams',
  User: '/users',
  AIProvider: '/ai-providers',
  Model: '/models',
  ModelAssignment: '/models',
  Skill: '/skills',
  Board: '/boards/:id',
  Tag: '/boards/tags',
  Artifact: '/artifacts',
  TestRun: '/test-results',
  NotificationRule: '/notifications',
  MCPServer: '/mcp-servers',
  WorkflowDefinition: '/workflows',
  Regulation: '/compliance/regulations',
  CompliancePolicy: '/compliance/policies',
  Procedure: '/compliance/procedures',
  Practice: '/compliance/practices',
  ArchitectureDecision: '/compliance/architecture-decisions',
  Strategy: '/experimentation/strategies',
  KPI: '/experimentation/kpis',
  ComplianceExperiment: '/experimentation/experiments',
  ComplianceMetric: '/experimentation/metrics',
  KnowledgeEntry: '/knowledge',
  Connection: '/settings',
  Settings: '/settings',
  ApprovalRequest: '/approvals',
  AgentStep: '/pipelines/runs/:id',
  ModelSelected: '/pipelines/runs/:id',
  ModelCall: '/pipelines/runs/:id',
};

/** Extract the entity prefix from an event type, e.g. "ProjectCreated" -> "Project" */
function getEntityPrefix(eventType: string): string {
  // Handle multi-word prefixes first (longest match)
  const prefixes = Object.keys(RESOURCE_ROUTES).sort((a, b) => b.length - a.length);
  for (const prefix of prefixes) {
    if (eventType.startsWith(prefix)) return prefix;
  }
  return '';
}

/** Get a link path for an event's resource, or null if not linkable */
function getResourceLink(event: EventItem): string | null {
  const prefix = getEntityPrefix(event.event_type);
  const route = RESOURCE_ROUTES[prefix];
  if (!route) return null;

  // For pipeline stage and agent step events, use run_id from payload
  const RUN_ID_PREFIXES = ['PipelineStage', 'StageReport', 'AgentStep', 'ModelSelected', 'ModelCall'];
  if (RUN_ID_PREFIXES.includes(prefix)) {
    const runId = event.payload?.run_id as string | undefined;
    if (runId) return route.replace(':id', runId);
    return null;
  }

  const resourceId = event.payload?.resource_id as string | undefined;
  if (!resourceId) return null;

  if (route.includes(':id')) {
    return route.replace(':id', resourceId);
  }

  return route;
}

function getEventColor(eventType: string): string {
  for (const [suffix, color] of Object.entries(eventColor)) {
    if (eventType.endsWith(suffix)) return color;
  }
  return 'gray';
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(formatValue).join(', ');
  return JSON.stringify(value);
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function ExpandableEventRow({ event }: { event: EventItem }) {
  const [opened, setOpened] = useState(false);
  const hasPayload = event.payload && Object.keys(event.payload).length > 0;
  const resourceId = event.payload?.resource_id as string | undefined;
  const resourceLink = getResourceLink(event);

  return (
    <>
      <Table.Tr
        style={{ cursor: hasPayload ? 'pointer' : undefined }}
        onClick={() => hasPayload && setOpened((o) => !o)}
      >
        <Table.Td>
          <TimeAgo date={event.occurred_at} size="sm" />
        </Table.Td>
        <Table.Td>
          <Badge variant="light" color={getEventColor(event.event_type)}>
            {event.event_type}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Group gap={4}>
            <Text size="sm">{event.actor_id || '—'}</Text>
            {event.actor_type && (
              <Badge variant="dot" size="xs" color={
                event.actor_type === 'system' ? 'gray'
                : event.actor_type === 'agent' ? 'violet'
                : 'blue'
              }>
                {event.actor_type}
              </Badge>
            )}
          </Group>
        </Table.Td>
        <Table.Td>
          {resourceId ? (
            resourceLink ? (
              <Anchor
                component={Link}
                to={resourceLink}
                size="xs"
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
                style={{ maxWidth: 200, display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <Text size="xs" truncate style={{ maxWidth: 180 }}>{resourceId}</Text>
                <IconExternalLink size={12} />
              </Anchor>
            ) : (
              <Text size="xs" c="dimmed" truncate style={{ maxWidth: 200 }}>
                {resourceId}
              </Text>
            )
          ) : (
            <Text size="xs" c="dimmed">—</Text>
          )}
        </Table.Td>
        <Table.Td>
          {hasPayload ? (
            <ActionIcon variant="subtle" size="sm">
              {opened ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
            </ActionIcon>
          ) : (
            <Text size="xs" c="dimmed">—</Text>
          )}
        </Table.Td>
      </Table.Tr>
      {hasPayload && (
        <Table.Tr>
          <Table.Td colSpan={5} p={0} style={{ borderTop: 'none' }}>
            <Collapse in={opened}>
              <Paper p="sm" ml="md" mr="md" mb="xs" bg="var(--mantine-color-dark-7)" radius="sm">
                <Stack gap={4}>
                  {Object.entries(event.payload).map(([key, value]) => (
                    <Group key={key} gap="xs" wrap="nowrap" align="flex-start">
                      <Text size="xs" fw={500} c="dimmed" style={{ minWidth: 120, flexShrink: 0 }}>
                        {formatKey(key)}
                      </Text>
                      <Text size="xs" style={{ wordBreak: 'break-all' }}>
                        {formatValue(value)}
                      </Text>
                    </Group>
                  ))}
                  {event.correlation_id && (
                    <Group gap="xs" wrap="nowrap" align="flex-start">
                      <Text size="xs" fw={500} c="dimmed" style={{ minWidth: 120, flexShrink: 0 }}>
                        Correlation ID
                      </Text>
                      <Text size="xs" ff="monospace" style={{ wordBreak: 'break-all' }}>
                        {event.correlation_id}
                      </Text>
                    </Group>
                  )}
                </Stack>
              </Paper>
            </Collapse>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

export function Component() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const offset = (page - 1) * PAGE_SIZE;

  const { data: typesResp } = useEventsListEventTypes();
  const eventTypes = typesResp?.data ?? [];

  const queryParams = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (typeFilter) queryParams.set('event_type', typeFilter);

  const { data: eventsResp, isLoading } = useQuery({
    queryKey: ['events', 'all', page, typeFilter],
    queryFn: () =>
      customInstance<{ data: PaginatedEvents }>(`/api/v1/events/all?${queryParams.toString()}`),
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const body = eventsResp?.data as PaginatedEvents | undefined;
  const items: EventItem[] = body?.items ?? [];
  const total: number = body?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Event Explorer</Title>
        <Group gap="sm">
          <Select
            placeholder="Filter by type"
            clearable
            searchable
            data={eventTypes.map((t: string) => t)}
            value={typeFilter}
            onChange={(v) => { setTypeFilter(v); setPage(1); }}
            w={280}
          />
          {total > 0 && (
            <Text size="sm" c="dimmed">{total.toLocaleString()} events</Text>
          )}
        </Group>
      </Group>

      {items.length === 0 && page === 1 ? (
        <EmptyState
          title="No events yet"
          description="Events will appear as operations are performed across the system."
        />
      ) : (
        <>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Timestamp</Table.Th>
                <Table.Th>Event Type</Table.Th>
                <Table.Th>Actor</Table.Th>
                <Table.Th>Resource</Table.Th>
                <Table.Th w={40}>Payload</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {items.map((e) => (
                <ExpandableEventRow key={e.event_id} event={e} />
              ))}
            </Table.Tbody>
          </Table>
          {totalPages > 1 && (
            <Center>
              <Pagination value={page} onChange={setPage} total={totalPages} />
            </Center>
          )}
        </>
      )}
    </Stack>
  );
}
