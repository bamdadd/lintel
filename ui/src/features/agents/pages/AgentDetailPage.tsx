import { useParams, useNavigate } from 'react-router';
import {
  Title,
  Stack,
  Paper,
  Badge,
  Group,
  Button,
  Loader,
  Center,
  TextInput,
  Textarea,
  NumberInput,
  MultiSelect,
  Tabs,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useAgentsGetAgentDefinition,
  useAgentsUpdateAgentDefinition,
} from '@/generated/api/agents/agents';
import { useSkillsListSkills } from '@/generated/api/skills/skills';

interface AgentDef {
  agent_id: string;
  name: string;
  description: string;
  system_prompt: string;
  allowed_skills?: string[];
  allowed_skill_ids?: string[];
  role: string;
  is_builtin?: boolean;
  model_policy?: {
    provider: string;
    model_name: string;
    max_tokens: number;
    temperature: number;
  };
  model_provider?: string;
  model_name?: string;
  max_tokens?: number;
  temperature?: number;
}

export function Component() {
  const { role: agentId } = useParams<{ role: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: defResp, isLoading } = useAgentsGetAgentDefinition(
    agentId ?? '',
    { query: { enabled: !!agentId } },
  );
  const { data: skillsResp } = useSkillsListSkills();

  const updateDefMutation = useAgentsUpdateAgentDefinition();

  const definition = defResp?.data as AgentDef | undefined;
  const availableSkills = (
    (skillsResp?.data ?? []) as Array<{ skill_id: string; name: string }>
  ).map((s) => ({ value: s.skill_id, label: s.name || s.skill_id }));

  const defForm = useForm({
    initialValues: {
      name: definition?.name ?? '',
      description: definition?.description ?? '',
      system_prompt: definition?.system_prompt ?? '',
      allowed_skills: definition?.allowed_skills ?? definition?.allowed_skill_ids ?? [],
      provider: definition?.model_policy?.provider ?? definition?.model_provider ?? 'anthropic',
      model_name: definition?.model_policy?.model_name ?? definition?.model_name ?? '',
      max_tokens: definition?.model_policy?.max_tokens ?? definition?.max_tokens ?? 4096,
      temperature: definition?.model_policy?.temperature ?? definition?.temperature ?? 0,
    },
  });

  // Sync form values when data loads
  if (definition && !defForm.isDirty()) {
    defForm.setValues({
      name: definition.name,
      description: definition.description ?? '',
      system_prompt: definition.system_prompt ?? '',
      allowed_skills: definition.allowed_skills ?? definition.allowed_skill_ids ?? [],
      provider: definition.model_policy?.provider ?? definition.model_provider ?? 'anthropic',
      model_name: definition.model_policy?.model_name ?? definition.model_name ?? '',
      max_tokens: definition.model_policy?.max_tokens ?? definition.max_tokens ?? 4096,
      temperature: definition.model_policy?.temperature ?? definition.temperature ?? 0,
    });
  }

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const handleSubmit = defForm.onSubmit((values) => {
    const { provider, model_name, max_tokens, temperature, ...rest } = values;
    updateDefMutation.mutate(
      {
        agentId: agentId ?? '',
        data: {
          ...rest,
          model_policy: { provider, model_name, max_tokens, temperature },
        },
      },
      {
        onSuccess: () => {
          notifications.show({
            title: 'Saved',
            message: 'Agent definition updated',
            color: 'green',
          });
          void queryClient.invalidateQueries({
            queryKey: ['/api/v1/agents/definitions'],
          });
        },
        onError: () => {
          notifications.show({
            title: 'Error',
            message: 'Failed to update definition',
            color: 'red',
          });
        },
      },
    );
  });

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/agents')}>
          &larr; Back
        </Button>
        <Title order={2}>{definition?.name ?? agentId}</Title>
        {definition?.role && <Badge size="lg">{definition.role}</Badge>}
        {definition?.is_builtin && (
          <Badge variant="light" color="gray" size="sm">built-in</Badge>
        )}
      </Group>

      <Tabs defaultValue="definition">
        <Tabs.List>
          <Tabs.Tab value="definition">Definition</Tabs.Tab>
          <Tabs.Tab value="model">Model Policy</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="definition" pt="md">
          <Paper withBorder p="lg" radius="md">
            <form onSubmit={handleSubmit}>
              <Stack gap="sm">
                <TextInput
                  label="Name"
                  placeholder="Agent name"
                  {...defForm.getInputProps('name')}
                />
                <Textarea
                  label="Description"
                  placeholder="What this agent does"
                  autosize
                  minRows={2}
                  {...defForm.getInputProps('description')}
                />
                <Textarea
                  label="System Prompt"
                  placeholder="You are a ..."
                  autosize
                  minRows={8}
                  styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
                  {...defForm.getInputProps('system_prompt')}
                />
                <MultiSelect
                  label="Allowed Skills"
                  placeholder="Select skills this agent can use"
                  data={availableSkills}
                  searchable
                  {...defForm.getInputProps('allowed_skills')}
                />
                <Group>
                  <Button
                    type="submit"
                    loading={updateDefMutation.isPending}
                  >
                    Update Definition
                  </Button>
                </Group>
              </Stack>
            </form>
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="model" pt="md">
          <Paper withBorder p="lg" radius="md">
            <form onSubmit={handleSubmit}>
              <Stack gap="sm">
                <TextInput
                  label="Provider"
                  {...defForm.getInputProps('provider')}
                />
                <TextInput
                  label="Model Name"
                  {...defForm.getInputProps('model_name')}
                />
                <NumberInput
                  label="Max Tokens"
                  min={1}
                  {...defForm.getInputProps('max_tokens')}
                />
                <NumberInput
                  label="Temperature"
                  min={0}
                  max={2}
                  step={0.1}
                  decimalScale={2}
                  {...defForm.getInputProps('temperature')}
                />
                <Group>
                  <Button
                    type="submit"
                    loading={updateDefMutation.isPending}
                  >
                    Save
                  </Button>
                </Group>
              </Stack>
            </form>
          </Paper>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
