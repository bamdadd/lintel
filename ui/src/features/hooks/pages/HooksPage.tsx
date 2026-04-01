import { useState } from 'react';
import {
  Title, Stack, Button, Group, Modal, Paper, Text, Badge, ActionIcon,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconWebhook, IconShieldCheck, IconPlayerPlay, IconClock,
} from '@tabler/icons-react';
import { EmptyState } from '@/shared/components/EmptyState';
import { useHooksStore } from '../hooks-store';
import { HookForm } from '../components/HookForm';
import type { HookFormValues } from '../components/HookForm';
import type { Hook, HookType } from '../types';

const HOOK_TYPE_META: Record<HookType, { icon: typeof IconShieldCheck; color: string; label: string }> = {
  pre: { icon: IconShieldCheck, color: 'red', label: 'Pre-hook' },
  post: { icon: IconPlayerPlay, color: 'blue', label: 'Post-hook' },
  scheduled: { icon: IconClock, color: 'orange', label: 'Scheduled' },
};

const ACTION_META: Record<string, { icon: typeof IconWebhook; color: string; label: string }> = {
  trigger_workflow: { icon: IconPlayerPlay, color: 'teal', label: 'Trigger Workflow' },
  webhook: { icon: IconWebhook, color: 'violet', label: 'Webhook' },
};

export function Component() {
  const { hooks, createHook, updateHook, deleteHook } = useHooksStore();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<Hook | null>(null);

  const handleCreate = (values: HookFormValues) => {
    createHook({
      ...values,
      conditions: values.conditions.trim() ? JSON.parse(values.conditions) : null,
      params_template: values.params_template.trim() ? JSON.parse(values.params_template) : null,
    });
    notifications.show({ title: 'Created', message: 'Hook created', color: 'green' });
    close();
  };

  const handleUpdate = (values: HookFormValues) => {
    if (!editItem) return;
    updateHook(editItem.hook_id, {
      ...values,
      conditions: values.conditions.trim() ? JSON.parse(values.conditions) : null,
      params_template: values.params_template.trim() ? JSON.parse(values.params_template) : null,
    });
    notifications.show({ title: 'Updated', message: 'Hook updated', color: 'green' });
    setEditItem(null);
  };

  const handleDelete = (id: string) => {
    deleteHook(id);
    notifications.show({ title: 'Deleted', message: 'Hook removed', color: 'orange' });
    if (editItem?.hook_id === id) setEditItem(null);
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Hooks</Title>
        <Button onClick={open}>Create Hook</Button>
      </Group>

      {hooks.length === 0 ? (
        <EmptyState
          title="No hooks configured"
          description="Create hooks to run pre/post actions on domain events"
          actionLabel="Create Hook"
          onAction={open}
        />
      ) : (
        <Stack gap="xs">
          {hooks.map((h) => {
            const typeMeta = HOOK_TYPE_META[h.hook_type] ?? HOOK_TYPE_META.post;
            const actionMeta = ACTION_META[h.action_type] ?? ACTION_META.trigger_workflow;
            const TypeIcon = typeMeta.icon;
            return (
              <Paper
                key={h.hook_id}
                withBorder
                p="sm"
                style={{ cursor: 'pointer' }}
                onClick={() => setEditItem(h)}
              >
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="sm" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                    <TypeIcon
                      size={20}
                      color={`var(--mantine-color-${typeMeta.color}-6)`}
                      style={{ flexShrink: 0 }}
                    />
                    <Stack gap={2} style={{ minWidth: 0 }}>
                      <Group gap="xs">
                        <Text fw={500} size="sm" truncate>
                          {h.name}
                        </Text>
                        <Badge color={typeMeta.color} variant="light" size="xs">
                          {typeMeta.label}
                        </Badge>
                        <Badge color={actionMeta.color} variant="outline" size="xs">
                          {actionMeta.label}
                        </Badge>
                        {!h.enabled && (
                          <Badge color="gray" variant="outline" size="xs">
                            Disabled
                          </Badge>
                        )}
                      </Group>
                      <Text size="xs" c="dimmed" truncate>
                        Pattern: {h.event_pattern}
                        {h.workflow_id && ` \u2192 ${h.workflow_id}`}
                        {h.webhook_url && ` \u2192 ${h.webhook_url}`}
                      </Text>
                    </Stack>
                  </Group>
                  <Group gap="xs" wrap="nowrap">
                    <Badge color={h.enabled ? 'green' : 'gray'} size="sm">
                      {h.enabled ? 'On' : 'Off'}
                    </Badge>
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(h.hook_id);
                      }}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Group>
              </Paper>
            );
          })}
        </Stack>
      )}

      <Modal opened={opened} onClose={close} title="Create Hook" size="lg">
        <HookForm onSubmit={handleCreate}>
          <Button type="submit">Create</Button>
        </HookForm>
      </Modal>

      <Modal
        opened={!!editItem}
        onClose={() => setEditItem(null)}
        title={`Edit: ${editItem?.name ?? ''}`}
        size="lg"
      >
        <HookForm hook={editItem} onSubmit={handleUpdate}>
          <Button type="submit">Save</Button>
        </HookForm>
      </Modal>
    </Stack>
  );
}
