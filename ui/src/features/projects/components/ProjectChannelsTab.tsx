import { useState, useEffect, useCallback } from 'react';
import {
  Stack, Paper, Text, Group, Badge, Loader, Center,
  MultiSelect, Switch, Alert,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlug, IconPlugOff } from '@tabler/icons-react';
import {
  listChannelConnectionDetails,
  updateChannelConnection,
} from '@/features/channels/channelsApi';
import type { ChannelConnectionDetail } from '@/features/channels/channelsApi';

interface WorkflowDef {
  definition_id: string;
  name: string;
  enabled: boolean;
}

interface Props {
  projectId: string;
  workflows: WorkflowDef[];
}

export function ProjectChannelsTab({ projectId, workflows }: Props) {
  const [connections, setConnections] = useState<ChannelConnectionDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    try {
      const data = await listChannelConnectionDetails();
      setConnections(data);
    } catch {
      setError('Failed to load channel connections');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchConnections();
  }, [fetchConnections]);

  const isLinked = (conn: ChannelConnectionDetail) =>
    conn.project_ids.includes(projectId);

  const handleToggleLink = async (conn: ChannelConnectionDetail) => {
    setSaving(conn.id);
    setError(null);
    try {
      const linked = isLinked(conn);
      const newProjectIds = linked
        ? conn.project_ids.filter((id) => id !== projectId)
        : [...conn.project_ids, projectId];
      const newAllowedWorkflows = linked ? conn.allowed_workflows : conn.allowed_workflows;
      await updateChannelConnection(conn.id, {
        project_ids: newProjectIds,
        allowed_workflows: newAllowedWorkflows,
      });
      notifications.show({
        title: linked ? 'Unlinked' : 'Linked',
        message: `Connection ${conn.provider}/${conn.channel_id} ${linked ? 'removed from' : 'added to'} project`,
        color: linked ? 'orange' : 'green',
      });
      await fetchConnections();
    } catch {
      setError('Failed to update connection');
    } finally {
      setSaving(null);
    }
  };

  const handleWorkflowChange = async (conn: ChannelConnectionDetail, workflowIds: string[]) => {
    setSaving(conn.id);
    setError(null);
    try {
      await updateChannelConnection(conn.id, { allowed_workflows: workflowIds });
      notifications.show({
        title: 'Updated',
        message: 'Allowed workflows updated',
        color: 'green',
      });
      await fetchConnections();
    } catch {
      setError('Failed to update workflows');
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <Center py="xl"><Loader /></Center>;

  const workflowOptions = workflows.map((w) => ({
    value: w.definition_id,
    label: `${w.name}${w.enabled ? '' : ' (disabled)'}`,
  }));

  if (connections.length === 0) {
    return (
      <Paper withBorder p="lg" radius="md">
        <Text c="dimmed" ta="center" py="xl">
          No channel connections configured. Add connections in Settings &rarr; Channels first.
        </Text>
      </Paper>
    );
  }

  return (
    <Stack gap="md">
      {error && <Alert color="red" title="Error" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {connections.map((conn) => {
        const linked = isLinked(conn);
        return (
          <Paper key={conn.id} withBorder p="md" radius="md">
            <Stack gap="sm">
              <Group justify="space-between">
                <Group gap="xs">
                  {linked
                    ? <IconPlug size={18} color="var(--mantine-color-green-6)" />
                    : <IconPlugOff size={18} color="var(--mantine-color-gray-5)" />}
                  <Text fw={600}>{conn.provider}</Text>
                  <Badge size="sm" variant="light">{conn.channel_id}</Badge>
                  {conn.workspace_id && (
                    <Badge size="sm" variant="outline" color="gray">{conn.workspace_id}</Badge>
                  )}
                </Group>
                <Switch
                  checked={linked}
                  onChange={() => void handleToggleLink(conn)}
                  label={linked ? 'Linked' : 'Not linked'}
                  disabled={saving === conn.id}
                />
              </Group>

              {linked && (
                <MultiSelect
                  label="Allowed workflows"
                  description="Which workflows this connection can trigger. Leave empty to allow all."
                  data={workflowOptions}
                  value={conn.allowed_workflows}
                  onChange={(values) => void handleWorkflowChange(conn, values)}
                  searchable
                  clearable
                  disabled={saving === conn.id}
                  placeholder="All workflows allowed"
                />
              )}
            </Stack>
          </Paper>
        );
      })}

      <Text size="xs" c="dimmed">
        Manage channel connections in Settings &rarr; Channels.
        Link them here to control which bots can trigger workflows for this project.
      </Text>
    </Stack>
  );
}
