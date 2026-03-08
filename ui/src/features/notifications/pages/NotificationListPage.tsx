import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch, MultiSelect,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications as notify } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useNotificationsListNotificationRules,
  useNotificationsCreateNotificationRule,
  useNotificationsUpdateNotificationRule,
  useNotificationsDeleteNotificationRule,
} from '@/generated/api/notifications/notifications';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { EmptyState } from '@/shared/components/EmptyState';
import type { NotificationChannel } from '@/generated/models/notificationChannel';

interface RuleItem {
  rule_id: string;
  project_id: string;
  event_types: string[];
  channel: string;
  target: string;
  enabled: boolean;
}

interface ProjectItem { project_id: string; name: string; }

const EVENT_TYPES = [
  'workflow.started', 'workflow.completed', 'workflow.failed',
  'approval.requested', 'approval.granted', 'approval.rejected',
  'pipeline.started', 'pipeline.completed', 'pipeline.failed',
  'code.pushed', 'pr.opened', 'pr.merged',
];

export function Component() {
  const { data: resp, isLoading } = useNotificationsListNotificationRules();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = useNotificationsCreateNotificationRule();
  const updateMut = useNotificationsUpdateNotificationRule();
  const deleteMut = useNotificationsDeleteNotificationRule();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editRule, setEditRule] = useState<RuleItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: {
      project_id: '',
      event_types: [] as string[],
      channel: 'slack',
      target: '',
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const rules = (resp?.data ?? []) as RuleItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      { data: { ...values, channel: values.channel as NotificationChannel } },
      {
        onSuccess: () => {
          notify.show({ title: 'Created', message: 'Notification rule added', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/notifications/rules'] });
          form.reset();
          close();
        },
        onError: () => notify.show({ title: 'Error', message: 'Failed to create rule', color: 'red' }),
      },
    );
  });

  const openEdit = (rule: RuleItem) => {
    setEditRule(rule);
  };

  const toggleEnabled = (rule: RuleItem) => {
    updateMut.mutate(
      { ruleId: rule.rule_id, data: { enabled: !rule.enabled } },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/notifications/rules'] });
        },
      },
    );
  };

  const handleEditSave = () => {
    if (!editRule) return;
    updateMut.mutate(
      { ruleId: editRule.rule_id, data: { target: editRule.target } },
      {
        onSuccess: () => {
          notify.show({ title: 'Updated', message: 'Rule updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/notifications/rules'] });
          setEditRule(null);
        },
      },
    );
  };

  const handleDelete = (ruleId: string) => {
    deleteMut.mutate(
      { ruleId },
      {
        onSuccess: () => {
          notify.show({ title: 'Deleted', message: 'Rule removed', color: 'orange' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/notifications/rules'] });
          if (editRule?.rule_id === ruleId) setEditRule(null);
        },
      },
    );
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? id;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Notification Rules</Title>
        <Button onClick={open}>Create Rule</Button>
      </Group>

      {rules.length === 0 ? (
        <EmptyState
          title="No notification rules"
          description="Set up rules to get notified about events"
          actionLabel="Create Rule"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Project</Table.Th>
              <Table.Th>Events</Table.Th>
              <Table.Th>Channel</Table.Th>
              <Table.Th>Target</Table.Th>
              <Table.Th>Enabled</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rules.map((r) => (
              <Table.Tr key={r.rule_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(r)}>
                <Table.Td>{projectName(r.project_id)}</Table.Td>
                <Table.Td>
                  <Group gap={4}>{r.event_types?.map((e) => <Badge key={e} size="sm" variant="light">{e}</Badge>)}</Group>
                </Table.Td>
                <Table.Td><Badge>{r.channel}</Badge></Table.Td>
                <Table.Td>{r.target}</Table.Td>
                <Table.Td>
                  <Switch checked={r.enabled} onChange={(e) => { e.stopPropagation(); toggleEnabled(r); }} />
                </Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(r.rule_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Notification Rule">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select label="Project" placeholder="Select project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <MultiSelect label="Event Types" placeholder="Select events" data={EVENT_TYPES} searchable {...form.getInputProps('event_types')} />
            <Select label="Channel" data={[{ value: 'slack', label: 'Slack' }, { value: 'email', label: 'Email' }, { value: 'webhook', label: 'Webhook' }]} {...form.getInputProps('channel')} />
            <TextInput label="Target" placeholder="#channel or email or URL" {...form.getInputProps('target')} />
            <Button type="submit" loading={createMut.isPending}>Create Rule</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editRule} onClose={() => setEditRule(null)} title="Edit Notification Rule">
        <Stack gap="sm">
          <TextInput label="Target" value={editRule?.target ?? ''} onChange={(e) => setEditRule((prev) => prev ? { ...prev, target: e.currentTarget.value } : null)} />
          <Button onClick={handleEditSave} loading={updateMut.isPending}>Save</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
