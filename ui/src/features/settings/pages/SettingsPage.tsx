import {
  Title,
  Stack,
  Tabs,
  Table,
  Loader,
  Center,
  Switch,
  TextInput,
  NumberInput,
} from '@mantine/core';
import {
  useSettingsListConnections,
  useSettingsGetSettings,
  useSettingsUpdateSettings,
  getSettingsGetSettingsQueryKey,
} from '@/generated/api/settings/settings';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { EmptyState } from '@/shared/components/EmptyState';
import { useQueryClient } from '@tanstack/react-query';

interface SettingsData {
  workspace_name?: string;
  default_model_provider?: string;
  pii_detection_enabled?: boolean;
  sandbox_enabled?: boolean;
  max_concurrent_workflows?: number;
  max_sandboxes?: number;
}

export function Component() {
  const { data: connResp, isLoading: connLoading } = useSettingsListConnections();
  const { data: settingsResp, isLoading: settingsLoading } = useSettingsGetSettings();
  const updateMutation = useSettingsUpdateSettings();
  const queryClient = useQueryClient();

  const connections = connResp?.data;
  const settings = settingsResp?.data as SettingsData | undefined;

  const handleToggle = (field: string, value: boolean) => {
    updateMutation.mutate(
      { data: { [field]: value } },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: getSettingsGetSettingsQueryKey() });
        },
      },
    );
  };

  const handleNumber = (field: string, value: number | string) => {
    const num = typeof value === 'string' ? parseInt(value, 10) : value;
    if (isNaN(num)) return;
    updateMutation.mutate(
      { data: { [field]: num } },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: getSettingsGetSettingsQueryKey() });
        },
      },
    );
  };

  if (connLoading || settingsLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Title order={2}>Settings</Title>
      <Tabs defaultValue="connections">
        <Tabs.List>
          <Tabs.Tab value="connections">Connections</Tabs.Tab>
          <Tabs.Tab value="general">General</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="connections" pt="md">
          {!connections || connections.length === 0 ? (
            <EmptyState
              title="No connections"
              description="Register external connections to enable integrations."
            />
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>ID</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {connections.map((c, i) => (
                  <Table.Tr key={i}>
                    <Table.Td>{String(c.connection_id ?? '')}</Table.Td>
                    <Table.Td>{String(c.connection_type ?? '')}</Table.Td>
                    <Table.Td>{String(c.name ?? '')}</Table.Td>
                    <Table.Td>
                      <StatusBadge status={String(c.status ?? 'untested')} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="general" pt="md">
          <Stack gap="sm" maw={400}>
            <TextInput
              label="Workspace Name"
              value={settings?.workspace_name ?? ''}
              readOnly
            />
            <TextInput
              label="Default Model Provider"
              value={settings?.default_model_provider ?? ''}
              readOnly
            />
            <Switch
              label="PII Detection Enabled"
              checked={settings?.pii_detection_enabled ?? true}
              onChange={(e) =>
                handleToggle('pii_detection_enabled', e.currentTarget.checked)
              }
            />
            <Switch
              label="Sandbox Enabled"
              checked={settings?.sandbox_enabled ?? true}
              onChange={(e) =>
                handleToggle('sandbox_enabled', e.currentTarget.checked)
              }
            />
            <NumberInput
              label="Max Concurrent Workflows"
              description="Maximum number of workflows that can run simultaneously"
              value={settings?.max_concurrent_workflows ?? 10}
              min={1}
              max={100}
              onBlur={(e) => handleNumber('max_concurrent_workflows', e.currentTarget.value)}
            />
            <NumberInput
              label="Max Sandboxes"
              description="Maximum number of sandboxes allowed. Oldest inactive sandbox is evicted when limit is reached."
              value={settings?.max_sandboxes ?? 20}
              min={1}
              max={200}
              onBlur={(e) => handleNumber('max_sandboxes', e.currentTarget.value)}
            />
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
