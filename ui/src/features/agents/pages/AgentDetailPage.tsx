import { useParams, useNavigate } from 'react-router';
import {
  Title,
  Stack,
  Paper,
  Text,
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
  useAgentsGetModelPolicy,
  useAgentsUpdateModelPolicy,
  useAgentsGetAgentDefinition,
  useAgentsCreateAgentDefinition,
  useAgentsUpdateAgentDefinition,
} from '@/generated/api/agents/agents';
import { useSkillsListSkills } from '@/generated/api/skills/skills';

interface AgentDef {
  agent_id: string;
  name: string;
  description: string;
  system_prompt: string;
  allowed_skills: string[];
  role: string;
  model_policy: { provider: string; model_name: string; max_tokens: number; temperature: number };
}

export function Component() {
  const { role } = useParams<{ role: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: policyResp, isLoading: policyLoading } = useAgentsGetModelPolicy(role ?? '', {
    query: { enabled: !!role },
  });
  const { data: defResp, isLoading: defLoading } = useAgentsGetAgentDefinition(role ?? '', {
    query: { enabled: !!role, retry: false },
  });
  const { data: skillsResp } = useSkillsListSkills();

  const policyMutation = useAgentsUpdateModelPolicy();
  const createDefMutation = useAgentsCreateAgentDefinition();
  const updateDefMutation = useAgentsUpdateAgentDefinition();

  const policy = policyResp?.data as
    | { provider?: string; model_name?: string; max_tokens?: number; temperature?: number }
    | undefined;

  const definition = defResp?.data as AgentDef | undefined;
  const availableSkills = ((skillsResp?.data ?? []) as Array<{ skill_id: string; name: string }>).map(
    (s) => ({ value: s.skill_id, label: s.name || s.skill_id }),
  );

  const policyForm = useForm({
    initialValues: {
      provider: policy?.provider ?? 'anthropic',
      model_name: policy?.model_name ?? '',
      max_tokens: policy?.max_tokens ?? 4096,
      temperature: policy?.temperature ?? 0,
    },
  });

  const defForm = useForm({
    initialValues: {
      name: definition?.name ?? (role ?? ''),
      description: definition?.description ?? '',
      system_prompt: definition?.system_prompt ?? '',
      allowed_skills: definition?.allowed_skills ?? [],
    },
  });

  // Sync form values when data loads
  if (policy && !policyForm.isDirty()) {
    policyForm.setValues({
      provider: policy.provider ?? 'anthropic',
      model_name: policy.model_name ?? '',
      max_tokens: policy.max_tokens ?? 4096,
      temperature: policy.temperature ?? 0,
    });
  }
  if (definition && !defForm.isDirty()) {
    defForm.setValues({
      name: definition.name,
      description: definition.description ?? '',
      system_prompt: definition.system_prompt ?? '',
      allowed_skills: definition.allowed_skills ?? [],
    });
  }

  if (policyLoading || defLoading) return <Center py="xl"><Loader /></Center>;

  const handlePolicySubmit = policyForm.onSubmit((values) => {
    policyMutation.mutate(
      { role: role ?? '', data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Saved', message: 'Model policy updated', color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/agents/policies'] });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update policy', color: 'red' });
        },
      },
    );
  });

  const handleDefSubmit = defForm.onSubmit((values) => {
    const payload = {
      ...values,
      agent_id: role ?? '',
      role: role ?? '',
      model_policy: {
        provider: policyForm.values.provider,
        model_name: policyForm.values.model_name,
        max_tokens: policyForm.values.max_tokens,
        temperature: policyForm.values.temperature,
      },
    };

    if (definition) {
      updateDefMutation.mutate(
        { agentId: role ?? '', data: values },
        {
          onSuccess: () => {
            notifications.show({ title: 'Saved', message: 'Agent definition updated', color: 'green' });
            void queryClient.invalidateQueries({ queryKey: ['/api/v1/agents/definitions'] });
          },
          onError: () => {
            notifications.show({ title: 'Error', message: 'Failed to update definition', color: 'red' });
          },
        },
      );
    } else {
      createDefMutation.mutate(
        { data: payload },
        {
          onSuccess: () => {
            notifications.show({ title: 'Created', message: 'Agent definition created', color: 'green' });
            void queryClient.invalidateQueries({ queryKey: ['/api/v1/agents/definitions'] });
          },
          onError: () => {
            notifications.show({ title: 'Error', message: 'Failed to create definition', color: 'red' });
          },
        },
      );
    }
  });

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/agents')}>
          &larr; Back
        </Button>
        <Title order={2}>Agent: {role}</Title>
        <Badge size="lg">{role}</Badge>
      </Group>

      <Tabs defaultValue="definition">
        <Tabs.List>
          <Tabs.Tab value="definition">Definition</Tabs.Tab>
          <Tabs.Tab value="model">Model Policy</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="definition" pt="md">
          <Paper withBorder p="lg" radius="md">
            <form onSubmit={handleDefSubmit}>
              <Stack gap="sm">
                <TextInput label="Name" placeholder="Agent name" {...defForm.getInputProps('name')} />
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
                    loading={createDefMutation.isPending || updateDefMutation.isPending}
                  >
                    {definition ? 'Update Definition' : 'Create Definition'}
                  </Button>
                </Group>
              </Stack>
            </form>
          </Paper>
        </Tabs.Panel>

        <Tabs.Panel value="model" pt="md">
          <Paper withBorder p="lg" radius="md">
            <form onSubmit={handlePolicySubmit}>
              <Stack gap="sm">
                <TextInput label="Provider" {...policyForm.getInputProps('provider')} />
                <TextInput label="Model Name" {...policyForm.getInputProps('model_name')} />
                <NumberInput label="Max Tokens" min={1} {...policyForm.getInputProps('max_tokens')} />
                <NumberInput
                  label="Temperature"
                  min={0}
                  max={2}
                  step={0.1}
                  decimalScale={2}
                  {...policyForm.getInputProps('temperature')}
                />
                <Group>
                  <Button type="submit" loading={policyMutation.isPending}>Save Policy</Button>
                </Group>
              </Stack>
            </form>
          </Paper>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
