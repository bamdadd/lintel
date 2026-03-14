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
  { value: 'queue', label: 'Queue \u2014 one at a time, FIFO' },
  { value: 'allow', label: 'Allow \u2014 run all simultaneously' },
  { value: 'skip', label: 'Skip \u2014 drop if already running' },
  { value: 'cancel', label: 'Cancel \u2014 cancel in-flight, start new' },
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
