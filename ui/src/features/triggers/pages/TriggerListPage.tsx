import { useState } from 'react';
import {
  Title, Stack, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch, Textarea, Text, Paper,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconTrash, IconWebhook, IconBrandSlack, IconClock,
  IconGitPullRequest, IconHandClick,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useTriggersListTriggers,
  useTriggersCreateTrigger,
  useTriggersUpdateTrigger,
  useTriggersDeleteTrigger,
} from '@/generated/api/triggers/triggers';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import type { TriggerType } from '@/generated/models/triggerType';
import { EmptyState } from '@/shared/components/EmptyState';

interface TriggerItem {
  trigger_id: string;
  project_id: string;
  trigger_type: string;
  name: string;
  config: Record<string, unknown> | null;
  enabled: boolean;
}

interface ProjectItem { project_id: string; name: string; }

const TRIGGER_TYPES = [
  { value: 'slack_message', label: 'Slack Message' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'pr_event', label: 'PR Event' },
  { value: 'manual', label: 'Manual' },
];

const TRIGGER_META: Record<string, { icon: typeof IconWebhook; color: string; label: string; description: string }> = {
  slack_message: { icon: IconBrandSlack, color: 'grape', label: 'Slack Message', description: 'Fires when a matching Slack message is received' },
  webhook: { icon: IconWebhook, color: 'blue', label: 'Webhook', description: 'Fires on incoming HTTP webhook' },
  schedule: { icon: IconClock, color: 'orange', label: 'Schedule', description: 'Fires on a cron schedule' },
  pr_event: { icon: IconGitPullRequest, color: 'teal', label: 'PR Event', description: 'Fires on pull request activity' },
  manual: { icon: IconHandClick, color: 'gray', label: 'Manual', description: 'Triggered manually by a user' },
};

/** Summarise trigger config as a human-readable string. */
function configSummary(triggerType: string, config: Record<string, unknown> | null): string {
  if (!config || Object.keys(config).length === 0) return 'No configuration';
  switch (triggerType) {
    case 'schedule':
      return config.cron ? `Cron: ${config.cron as string}` : `${Object.keys(config).length} setting(s)`;
    case 'webhook':
      return config.path ? `Path: ${config.path as string}` : config.url ? `URL: ${config.url as string}` : `${Object.keys(config).length} setting(s)`;
    case 'slack_message':
      return config.channel ? `Channel: ${config.channel as string}` : config.pattern ? `Pattern: ${config.pattern as string}` : `${Object.keys(config).length} setting(s)`;
    case 'pr_event': {
      const parts: string[] = [];
      if (config.repo) parts.push(config.repo as string);
      if (config.actions) parts.push(`on ${(config.actions as string[]).join(', ')}`);
      return parts.length > 0 ? parts.join(' ') : `${Object.keys(config).length} setting(s)`;
    }
    default:
      return `${Object.keys(config).length} setting(s)`;
  }
}

export function Component() {
  const { data: resp, isLoading } = useTriggersListTriggers();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = useTriggersCreateTrigger();
  const updateMut = useTriggersUpdateTrigger();
  const deleteMut = useTriggersDeleteTrigger();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<TriggerItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: { project_id: '', trigger_type: 'manual', name: '', config: '' },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: { name: '', config: '', enabled: true },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const triggers = (resp?.data ?? []) as TriggerItem[];

  const handleCreate = form.onSubmit((values) => {
    let config: Record<string, unknown> | null = null;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON config', color: 'red' }); return; }
    }
    createMut.mutate(
      { data: { ...values, trigger_type: values.trigger_type as TriggerType, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Trigger created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/triggers'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create trigger', color: 'red' }),
      },
    );
  });

  const openEdit = (t: TriggerItem) => {
    setEditItem(t);
    editForm.setValues({ name: t.name, config: t.config ? JSON.stringify(t.config, null, 2) : '', enabled: t.enabled });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editItem) return;
    let config: Record<string, unknown> | undefined;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON config', color: 'red' }); return; }
    }
    updateMut.mutate(
      { triggerId: editItem.trigger_id, data: { name: values.name, config, enabled: values.enabled } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Trigger updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/triggers'] });
          setEditItem(null);
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' }),
      },
    );
  });

  const handleDelete = (id: string) => {
    deleteMut.mutate({ triggerId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Trigger removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/triggers'] });
        if (editItem?.trigger_id === id) setEditItem(null);
      },
    });
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? id;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Triggers</Title>
        <Button onClick={open}>Create Trigger</Button>
      </Group>

      {triggers.length === 0 ? (
        <EmptyState title="No triggers" description="Create triggers to automate workflows" actionLabel="Create Trigger" onAction={open} />
      ) : (
        <Stack gap="xs">
          {triggers.map((t) => {
            const meta = (TRIGGER_META[t.trigger_type] ?? TRIGGER_META.manual)!;
            const Icon = meta.icon;
            return (
              <Paper key={t.trigger_id} withBorder p="sm" style={{ cursor: 'pointer' }} onClick={() => openEdit(t)}>
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="sm" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                    <Icon size={20} color={`var(--mantine-color-${meta.color}-6)`} style={{ flexShrink: 0 }} />
                    <Stack gap={2} style={{ minWidth: 0 }}>
                      <Group gap="xs">
                        <Text fw={500} size="sm" truncate>{t.name}</Text>
                        <Badge color={meta.color} variant="light" size="xs">{meta.label}</Badge>
                        {!t.enabled && <Badge color="gray" variant="outline" size="xs">Disabled</Badge>}
                      </Group>
                      <Group gap="xs">
                        <Text size="xs" c="dimmed" truncate>{configSummary(t.trigger_type, t.config)}</Text>
                        <Text size="xs" c="dimmed">in {projectName(t.project_id)}</Text>
                      </Group>
                    </Stack>
                  </Group>
                  <Group gap="xs" wrap="nowrap">
                    <Badge color={t.enabled ? 'green' : 'gray'} size="sm">{t.enabled ? 'On' : 'Off'}</Badge>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(t.trigger_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Group>
              </Paper>
            );
          })}
        </Stack>
      )}

      <Modal opened={opened} onClose={close} title="Create Trigger">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My trigger" {...form.getInputProps('name')} />
            <Select label="Type" data={TRIGGER_TYPES} {...form.getInputProps('trigger_type')} />
            <Select label="Project" placeholder="Select project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Config (JSON)" placeholder='{"cron": "0 * * * *"}' minRows={3} styles={{ input: { fontFamily: 'monospace' } }} {...form.getInputProps('config')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`}>
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Switch label="Enabled" {...editForm.getInputProps('enabled', { type: 'checkbox' })} />
            <Textarea label="Config (JSON)" minRows={3} styles={{ input: { fontFamily: 'monospace' } }} {...editForm.getInputProps('config')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
