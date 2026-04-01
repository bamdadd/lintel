import { useParams, useNavigate } from 'react-router';
import {
  Title, Stack, Button, Group, Paper, Text, Badge, Code,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconArrowLeft } from '@tabler/icons-react';
import { useHooksStore } from '../hooks-store';
import { HookForm } from '../components/HookForm';
import type { HookFormValues } from '../components/HookForm';

export function Component() {
  const { hookId } = useParams<{ hookId: string }>();
  const navigate = useNavigate();
  const { getHook, updateHook, deleteHook } = useHooksStore();
  const hook = hookId ? getHook(hookId) : null;

  if (!hook) {
    return (
      <Stack gap="md">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => void navigate('/hooks')}>
            Back
          </Button>
        </Group>
        <Text c="dimmed">Hook not found.</Text>
      </Stack>
    );
  }

  const handleUpdate = (values: HookFormValues) => {
    updateHook(hook.hook_id, {
      ...values,
      conditions: values.conditions.trim() ? JSON.parse(values.conditions) : null,
      params_template: values.params_template.trim() ? JSON.parse(values.params_template) : null,
    });
    notifications.show({ title: 'Updated', message: 'Hook saved', color: 'green' });
  };

  const handleDelete = () => {
    deleteHook(hook.hook_id);
    notifications.show({ title: 'Deleted', message: 'Hook removed', color: 'orange' });
    void navigate('/hooks');
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group>
          <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => void navigate('/hooks')}>
            Back
          </Button>
          <Title order={2}>{hook.name}</Title>
        </Group>
        <Button color="red" variant="outline" onClick={handleDelete}>
          Delete
        </Button>
      </Group>

      <Paper withBorder p="md">
        <Stack gap="xs">
          <Group gap="xs">
            <Badge>{hook.hook_type}</Badge>
            <Badge variant="outline">{hook.action_type}</Badge>
            <Badge color={hook.enabled ? 'green' : 'gray'}>{hook.enabled ? 'Enabled' : 'Disabled'}</Badge>
          </Group>
          <Text size="sm">
            Event pattern: <Code>{hook.event_pattern}</Code>
          </Text>
          {hook.workflow_id && <Text size="sm">Workflow: <Code>{hook.workflow_id}</Code></Text>}
          {hook.webhook_url && <Text size="sm">Webhook: <Code>{hook.webhook_url}</Code></Text>}
          <Text size="sm" c="dimmed">Max chain depth: {hook.max_chain_depth}</Text>
        </Stack>
      </Paper>

      <Paper withBorder p="md">
        <Title order={4} mb="sm">Edit Hook</Title>
        <HookForm hook={hook} onSubmit={handleUpdate}>
          <Button type="submit">Save Changes</Button>
        </HookForm>
      </Paper>
    </Stack>
  );
}
