import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Badge,
  ActionIcon,
  Loader,
  Center,
  MultiSelect,
  Stepper,
  Paper,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconCheck, IconFolder, IconRobot } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import {
  useProjectsListProjects,
  useProjectsCreateProject,
  useProjectsRemoveProject,
} from '@/generated/api/projects/projects';
import { useRepositoriesListRepositories } from '@/generated/api/repositories/repositories';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';
import { EmptyState } from '@/shared/components/EmptyState';
import { BotSetupStep } from '@/features/projects/components/BotSetupStep';
import type { BotSetupConfig } from '@/features/projects/components/BotSetupStep';
import { createBot, createBotScope } from '@/features/projects/api/botsApi';

interface Project {
  project_id: string;
  name: string;
  repo_ids: string[];
  status: string;
  default_branch: string;
}

const DEFAULT_BOT_CONFIG: BotSetupConfig = {
  mode: 'skip',
  botId: '',
  botName: '',
  channelId: '',
  workflowIds: [],
  agentRoles: [],
  triggerMode: 'mention',
};

export function Component() {
  const { data: resp, isLoading } = useProjectsListProjects();
  const { data: reposResp } = useRepositoriesListRepositories();
  const { data: workflowsResp } = useWorkflowDefinitionsListWorkflowDefinitions();
  const createMutation = useProjectsCreateProject();
  const deleteMutation = useProjectsRemoveProject();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [opened, { open, close }] = useDisclosure(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [botConfig, setBotConfig] = useState<BotSetupConfig>({ ...DEFAULT_BOT_CONFIG });
  const [saving, setSaving] = useState(false);

  const form = useForm({
    initialValues: {
      name: '',
      repo_ids: [] as string[],
      default_branch: 'main',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
      repo_ids: (v) => (v.length > 0 ? null : 'Select at least one repository'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const projects = (resp?.data ?? []) as unknown as Project[];
  const repos = (reposResp?.data ?? []) as Array<{ repo_id: string; name?: string; url?: string }>;
  const repoOptions = repos.map((r) => ({ value: r.repo_id, label: r.name ?? r.url ?? r.repo_id }));
  const workflows = (workflowsResp?.data ?? []) as unknown as { definition_id: string; name: string; enabled: boolean }[];

  const handleClose = () => {
    close();
    setWizardStep(0);
    setBotConfig({ ...DEFAULT_BOT_CONFIG });
    form.reset();
  };

  const handleNextFromBasicInfo = () => {
    const result = form.validate();
    if (result.hasErrors) return;
    setWizardStep(1);
  };

  async function configureBotScopes(projectId: string) {
    if (botConfig.mode === 'skip') return;

    let botId = botConfig.botId;

    if (botConfig.mode === 'new') {
      const bot = await createBot({
        name: botConfig.botName,
        platform: 'slack',
        scopes: [],
      });
      botId = bot.bot_id;
    }

    if (!botId) return;

    // Grant project scope
    await createBotScope({
      bot_id: botId,
      resource_type: 'project',
      resource_id: projectId,
    });

    // Grant workflow scopes
    for (const wfId of botConfig.workflowIds) {
      await createBotScope({
        bot_id: botId,
        resource_type: 'workflow',
        resource_id: wfId,
      });
    }

    // Grant agent role scopes
    for (const role of botConfig.agentRoles) {
      await createBotScope({
        bot_id: botId,
        resource_type: 'agent',
        resource_id: role,
      });
    }
  }

  const handleCreate = () => {
    const result = form.validate();
    if (result.hasErrors) {
      setWizardStep(0);
      return;
    }

    setSaving(true);
    createMutation.mutate(
      { data: form.values },
      {
        onSuccess: async (data) => {
          const projectId = (data as unknown as { project_id: string }).project_id;
          try {
            await configureBotScopes(projectId);
          } catch {
            notifications.show({
              title: 'Warning',
              message: 'Project created but bot setup failed. Configure the bot from the Channels tab.',
              color: 'yellow',
            });
          }
          notifications.show({ title: 'Created', message: `Project "${form.values.name}" created`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/projects'] });
          handleClose();
          setSaving(false);
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create project', color: 'red' });
          setSaving(false);
        },
      },
    );
  };

  const handleDelete = (projectId: string) => {
    deleteMutation.mutate(
      { projectId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Project removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/projects'] });
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Projects</Title>
        <Button onClick={open}>Create Project</Button>
      </Group>

      {projects.length === 0 ? (
        <EmptyState
          title="No projects"
          description="Create a project to link a repository to a workflow"
          actionLabel="Create Project"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Repositories</Table.Th>
              <Table.Th>Branch</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {projects.map((p) => (
              <Table.Tr key={p.project_id} style={{ cursor: 'pointer' }} onClick={() => void navigate(`/projects/${p.project_id}`)}>
                <Table.Td>{p.name}</Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {(p.repo_ids ?? []).map((id) => (
                      <Badge key={id} size="xs" variant="light">
                        {repos.find((r) => r.repo_id === id)?.name ?? id}
                      </Badge>
                    ))}
                    {(!p.repo_ids || p.repo_ids.length === 0) && '—'}
                  </Group>
                </Table.Td>
                <Table.Td>{p.default_branch}</Table.Td>
                <Table.Td><Badge>{p.status}</Badge></Table.Td>
                <Table.Td>
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    onClick={(e) => { e.stopPropagation(); handleDelete(p.project_id); }}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={handleClose} title="Create Project" size="lg">
        <Stepper active={wizardStep} onStepClick={setWizardStep} allowNextStepsSelect={false}>
          <Stepper.Step label="Basic Info" icon={<IconFolder size={18} />} completedIcon={<IconCheck size={18} />}>
            <Paper withBorder p="md" mt="md">
              <Stack gap="sm">
                <TextInput label="Name" placeholder="My Project" {...form.getInputProps('name')} />
                <MultiSelect
                  label="Repositories"
                  placeholder="Select repositories"
                  data={repoOptions}
                  searchable
                  {...form.getInputProps('repo_ids')}
                />
                <TextInput label="Default Branch" {...form.getInputProps('default_branch')} />
                <Group justify="flex-end">
                  <Button onClick={handleNextFromBasicInfo}>Next: Bot Setup</Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>

          <Stepper.Step label="Slack Bot" icon={<IconRobot size={18} />} completedIcon={<IconCheck size={18} />}>
            <Paper withBorder p="md" mt="md">
              <Stack gap="sm">
                <BotSetupStep config={botConfig} onChange={setBotConfig} workflows={workflows} />
                <Group justify="space-between">
                  <Button variant="default" onClick={() => setWizardStep(0)}>Back</Button>
                  <Button onClick={handleCreate} loading={saving || createMutation.isPending}>
                    Create Project
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>
        </Stepper>
      </Modal>
    </Stack>
  );
}
