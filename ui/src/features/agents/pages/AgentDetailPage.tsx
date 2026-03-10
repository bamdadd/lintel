import { useEffect, useState } from 'react';
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
  Text,
  TypographyStylesProvider,
  SegmentedControl,
  Box,
} from '@mantine/core';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
  max_tokens?: number;
  temperature?: number;
}

export function Component() {
  const { role: agentId } = useParams<{ role: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [descMode, setDescMode] = useState<'edit' | 'preview'>('preview');

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
      max_tokens: definition?.max_tokens ?? 4096,
      temperature: definition?.temperature ?? 0,
    },
  });

  // Sync form values when data loads
  useEffect(() => {
    if (definition && !defForm.isDirty()) {
      defForm.setValues({
        name: definition.name,
        description: definition.description ?? '',
        system_prompt: definition.system_prompt ?? '',
        allowed_skills: definition.allowed_skills ?? definition.allowed_skill_ids ?? [],
        max_tokens: definition.max_tokens ?? 4096,
        temperature: definition.temperature ?? 0,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definition]);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const handleSubmit = defForm.onSubmit((values) => {
    updateDefMutation.mutate(
      {
        agentId: agentId ?? '',
        data: values,
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
          <Tabs.Tab value="tuning">Tuning</Tabs.Tab>
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
                <Box>
                  <Group justify="space-between" mb={4}>
                    <Text size="sm" fw={500}>Description</Text>
                    <SegmentedControl
                      size="xs"
                      value={descMode}
                      onChange={(v) => setDescMode(v as 'edit' | 'preview')}
                      data={[
                        { label: 'Edit', value: 'edit' },
                        { label: 'Preview', value: 'preview' },
                      ]}
                    />
                  </Group>
                  {descMode === 'edit' ? (
                    <Textarea
                      placeholder="What this agent does (supports Markdown)"
                      autosize
                      minRows={6}
                      maxRows={20}
                      styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
                      {...defForm.getInputProps('description')}
                    />
                  ) : (
                    <Paper withBorder p="md" radius="sm" mih={120}>
                      {defForm.values.description ? (
                        <TypographyStylesProvider>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {defForm.values.description}
                          </ReactMarkdown>
                        </TypographyStylesProvider>
                      ) : (
                        <Text c="dimmed" size="sm" fs="italic">No description</Text>
                      )}
                    </Paper>
                  )}
                </Box>
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

        <Tabs.Panel value="tuning" pt="md">
          <Paper withBorder p="lg" radius="md">
            <Text size="sm" c="dimmed" mb="md">
              Model selection is configured via AI Providers. These are agent-specific generation parameters.
            </Text>
            <form onSubmit={handleSubmit}>
              <Stack gap="sm">
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
