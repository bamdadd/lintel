import { useState, useEffect } from 'react';
import {
  Stack, Paper, Text, Group, Button, TextInput, Select, MultiSelect,
  Alert, Badge, Divider, SegmentedControl,
} from '@mantine/core';
import { IconBrandSlack, IconAlertCircle, IconCheck, IconRobot } from '@tabler/icons-react';
import { listBots } from '@/features/projects/api/botsApi';
import type { Bot } from '@/features/projects/api/botsApi';

export type TriggerMode = 'mention' | 'channel' | 'thread';

export interface BotSetupConfig {
  mode: 'existing' | 'new' | 'skip';
  botId: string;
  botName: string;
  channelId: string;
  workflowIds: string[];
  agentRoles: string[];
  triggerMode: TriggerMode;
}

const TRIGGER_MODE_OPTIONS = [
  { value: 'mention', label: 'On @mention' },
  { value: 'channel', label: 'All channel messages' },
  { value: 'thread', label: 'Thread replies only' },
];

const AGENT_ROLE_OPTIONS = [
  { value: 'planner', label: 'Planner' },
  { value: 'coder', label: 'Coder' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'pm', label: 'PM' },
  { value: 'designer', label: 'Designer' },
  { value: 'summarizer', label: 'Summarizer' },
  { value: 'architect', label: 'Architect' },
  { value: 'qa_engineer', label: 'QA Engineer' },
  { value: 'devops', label: 'DevOps' },
  { value: 'security', label: 'Security' },
  { value: 'researcher', label: 'Researcher' },
  { value: 'tech_lead', label: 'Tech Lead' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'triage', label: 'Triage' },
];

interface WorkflowDef {
  definition_id: string;
  name: string;
}

interface Props {
  config: BotSetupConfig;
  onChange: (config: BotSetupConfig) => void;
  workflows: WorkflowDef[];
}

export function BotSetupStep({ config, onChange, workflows }: Props) {
  const [existingBots, setExistingBots] = useState<Bot[]>([]);
  const [loadingBots, setLoadingBots] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (config.mode === 'existing') {
      setLoadingBots(true);
      listBots()
        .then(setExistingBots)
        .catch(() => setError('Failed to load existing bots'))
        .finally(() => setLoadingBots(false));
    }
  }, [config.mode]);

  const update = (partial: Partial<BotSetupConfig>) =>
    onChange({ ...config, ...partial });

  const workflowOptions = workflows.map((w) => ({
    value: w.definition_id,
    label: w.name,
  }));

  const botOptions = existingBots
    .filter((b) => b.platform === 'slack')
    .map((b) => ({ value: b.bot_id, label: `${b.name} (${b.status})` }));

  return (
    <Stack gap="md">
      <Group gap="xs">
        <IconRobot size={20} />
        <Text fw={600}>Slack Bot Setup</Text>
        <Badge size="sm" variant="light" color="gray">Optional</Badge>
      </Group>

      <Text size="sm" c="dimmed">
        Connect a Slack bot to this project so workflows can be triggered from Slack channels.
        You can skip this step and configure it later from the project settings.
      </Text>

      <SegmentedControl
        value={config.mode}
        onChange={(v) => update({ mode: v as BotSetupConfig['mode'] })}
        data={[
          { value: 'skip', label: 'Skip for now' },
          { value: 'new', label: 'Add to Slack' },
          { value: 'existing', label: 'Use existing bot' },
        ]}
        fullWidth
      />

      {error && (
        <Alert color="red" icon={<IconAlertCircle size={16} />} withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {config.mode === 'new' && (
        <Paper withBorder p="md" radius="md">
          <Stack gap="sm">
            <TextInput
              label="Bot name"
              placeholder="my-project-bot"
              value={config.botName}
              onChange={(e) => update({ botName: e.currentTarget.value })}
              required
            />

            <Button
              component="a"
              href="/api/v1/settings/channels/slack/install"
              target="_blank"
              leftSection={<IconBrandSlack size={18} />}
              variant="outline"
              color="violet"
            >
              Add to Slack (OAuth)
            </Button>

            <Text size="xs" c="dimmed">
              Click above to authorize this bot in your Slack workspace via OAuth.
              After authorizing, return here to complete the configuration.
            </Text>

            <Divider label="Channel & Scope" labelPosition="center" />

            <TextInput
              label="Slack channel ID"
              placeholder="C01ABCDEF"
              description="The channel this bot should monitor"
              value={config.channelId}
              onChange={(e) => update({ channelId: e.currentTarget.value })}
            />

            <MultiSelect
              label="Allowed workflows"
              description="Which workflows this bot can trigger. Leave empty to allow all."
              data={workflowOptions}
              value={config.workflowIds}
              onChange={(v) => update({ workflowIds: v })}
              searchable
              clearable
              placeholder="All workflows"
            />

            <MultiSelect
              label="Agent roles"
              description="Which agent roles this bot can invoke. Leave empty to allow all."
              data={AGENT_ROLE_OPTIONS}
              value={config.agentRoles}
              onChange={(v) => update({ agentRoles: v })}
              searchable
              clearable
              placeholder="All roles"
            />

            <Select
              label="Trigger mode"
              description="How the bot should be activated in the channel"
              data={TRIGGER_MODE_OPTIONS}
              value={config.triggerMode}
              onChange={(v) => v && update({ triggerMode: v as TriggerMode })}
            />
          </Stack>
        </Paper>
      )}

      {config.mode === 'existing' && (
        <Paper withBorder p="md" radius="md">
          <Stack gap="sm">
            <Select
              label="Select a Slack bot"
              placeholder={loadingBots ? 'Loading...' : 'Choose a bot'}
              data={botOptions}
              value={config.botId}
              onChange={(v) => v && update({ botId: v })}
              searchable
              disabled={loadingBots}
              nothingFoundMessage="No Slack bots found"
            />

            {config.botId && (
              <>
                <Alert color="green" icon={<IconCheck size={16} />} variant="light">
                  Bot selected. Configure its scope for this project below.
                </Alert>

                <Divider label="Channel & Scope" labelPosition="center" />

                <TextInput
                  label="Slack channel ID"
                  placeholder="C01ABCDEF"
                  description="The channel this bot should monitor"
                  value={config.channelId}
                  onChange={(e) => update({ channelId: e.currentTarget.value })}
                />

                <MultiSelect
                  label="Allowed workflows"
                  description="Which workflows this bot can trigger. Leave empty to allow all."
                  data={workflowOptions}
                  value={config.workflowIds}
                  onChange={(v) => update({ workflowIds: v })}
                  searchable
                  clearable
                  placeholder="All workflows"
                />

                <MultiSelect
                  label="Agent roles"
                  description="Which agent roles this bot can invoke. Leave empty to allow all."
                  data={AGENT_ROLE_OPTIONS}
                  value={config.agentRoles}
                  onChange={(v) => update({ agentRoles: v })}
                  searchable
                  clearable
                  placeholder="All roles"
                />

                <Select
                  label="Trigger mode"
                  description="How the bot should be activated in the channel"
                  data={TRIGGER_MODE_OPTIONS}
                  value={config.triggerMode}
                  onChange={(v) => v && update({ triggerMode: v as TriggerMode })}
                />
              </>
            )}
          </Stack>
        </Paper>
      )}

      {config.mode === 'skip' && (
        <Alert color="blue" variant="light">
          You can add a Slack bot later from the project&apos;s Channels tab.
        </Alert>
      )}
    </Stack>
  );
}
