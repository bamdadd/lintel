import {
  Stack, TextInput, Select, Textarea, NumberInput, Switch, Text, Code,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useMemo } from 'react';
import type { Hook, HookType, HookActionType } from '../types';

const HOOK_TYPES: { value: HookType; label: string }[] = [
  { value: 'pre', label: 'Pre-hook (blocks until evaluated)' },
  { value: 'post', label: 'Post-hook (fire-and-forget)' },
  { value: 'scheduled', label: 'Scheduled' },
];

const ACTION_TYPES: { value: HookActionType; label: string }[] = [
  { value: 'trigger_workflow', label: 'Trigger Workflow' },
  { value: 'webhook', label: 'Webhook' },
];

export interface HookFormValues {
  name: string;
  event_pattern: string;
  hook_type: HookType;
  action_type: HookActionType;
  workflow_id: string;
  webhook_url: string;
  conditions: string;
  params_template: string;
  enabled: boolean;
  max_chain_depth: number;
  project_id: string;
}

function defaultValues(hook?: Hook | null): HookFormValues {
  return {
    name: hook?.name ?? '',
    event_pattern: hook?.event_pattern ?? '*',
    hook_type: hook?.hook_type ?? 'post',
    action_type: hook?.action_type ?? 'trigger_workflow',
    workflow_id: hook?.workflow_id ?? '',
    webhook_url: hook?.webhook_url ?? '',
    conditions: hook?.conditions ? JSON.stringify(hook.conditions, null, 2) : '',
    params_template: hook?.params_template ? JSON.stringify(hook.params_template, null, 2) : '',
    enabled: hook?.enabled ?? true,
    max_chain_depth: hook?.max_chain_depth ?? 5,
    project_id: hook?.project_id ?? '',
  };
}

/** Render a glob pattern preview showing example matches. */
function PatternPreview({ pattern }: { pattern: string }) {
  const examples = useMemo(() => {
    const events = [
      'PipelineRunStarted', 'PipelineRunCompleted', 'PipelineRunFailed',
      'WorkItemCreated', 'WorkItemUpdated',
      'PullRequestOpened', 'PullRequestMerged',
      'StageCompleted', 'StageFailed',
    ];
    if (!pattern || pattern === '*') return events;
    // Simple glob preview: convert glob to regex for client preview
    const re = new RegExp(
      '^' + pattern.replace(/\*/g, '.*').replace(/\?/g, '.') + '$',
    );
    return events.filter((e) => re.test(e));
  }, [pattern]);

  if (examples.length === 0) {
    return <Text size="xs" c="dimmed">No matching example events</Text>;
  }
  return (
    <Text size="xs" c="dimmed">
      Matches: {examples.map((e, i) => (
        <span key={e}>{i > 0 && ', '}<Code>{e}</Code></span>
      ))}
    </Text>
  );
}

interface HookFormProps {
  hook?: Hook | null;
  onSubmit: (values: HookFormValues) => void;
  loading?: boolean;
  children?: React.ReactNode;
}

export function HookForm({ hook, onSubmit, loading: _loading, children }: HookFormProps) {
  const form = useForm<HookFormValues>({
    initialValues: defaultValues(hook),
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      event_pattern: (v) => (v.trim() ? null : 'Required'),
      webhook_url: (v, values) =>
        values.action_type === 'webhook' && !v.trim() ? 'Required for webhook actions' : null,
      conditions: (v) => {
        if (!v.trim()) return null;
        try { JSON.parse(v); return null; } catch { return 'Invalid JSON'; }
      },
      params_template: (v) => {
        if (!v.trim()) return null;
        try { JSON.parse(v); return null; } catch { return 'Invalid JSON'; }
      },
    },
  });

  return (
    <form onSubmit={form.onSubmit(onSubmit)}>
      <Stack gap="sm">
        <TextInput label="Name" placeholder="Auto-review on PR" {...form.getInputProps('name')} />
        <TextInput
          label="Event Pattern"
          placeholder="Pipeline* or *Completed"
          description="Glob-style pattern: * matches any chars, ? matches single char"
          {...form.getInputProps('event_pattern')}
        />
        <PatternPreview pattern={form.values.event_pattern} />

        <Select
          label="Hook Type"
          data={HOOK_TYPES}
          {...form.getInputProps('hook_type')}
        />
        <Select
          label="Action Type"
          data={ACTION_TYPES}
          {...form.getInputProps('action_type')}
        />

        {form.values.action_type === 'trigger_workflow' && (
          <TextInput
            label="Workflow ID"
            placeholder="wf-review"
            {...form.getInputProps('workflow_id')}
          />
        )}
        {form.values.action_type === 'webhook' && (
          <TextInput
            label="Webhook URL"
            placeholder="https://hooks.example.com/notify"
            {...form.getInputProps('webhook_url')}
          />
        )}

        <Textarea
          label="Conditions (JSON)"
          placeholder='{"stage": "deploy"}'
          minRows={2}
          styles={{ input: { fontFamily: 'monospace' } }}
          {...form.getInputProps('conditions')}
        />
        <Textarea
          label="Params Template (JSON)"
          placeholder='{"repo": "{{ event.repo }}"}'
          description="Map event fields to workflow params using {{ event.field }} syntax"
          minRows={2}
          styles={{ input: { fontFamily: 'monospace' } }}
          {...form.getInputProps('params_template')}
        />

        <NumberInput
          label="Max Chain Depth"
          description="Prevents infinite hook loops"
          min={1}
          max={20}
          {...form.getInputProps('max_chain_depth')}
        />
        <Switch
          label="Enabled"
          {...form.getInputProps('enabled', { type: 'checkbox' })}
        />

        {children}
      </Stack>
    </form>
  );
}
