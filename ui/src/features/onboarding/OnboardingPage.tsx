import {
  Title, Stack, Progress, Paper, Group, Text, ThemeIcon, Loader, Center, Button,
} from '@mantine/core';
import {
  IconCheck, IconCircle, IconBrain, IconFolder, IconMessageCircle,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { useOnboardingGetOnboardingStatus } from '@/generated/api/onboarding/onboarding';

interface ChecklistItem {
  key: string;
  label: string;
  description: string;
  completed: boolean;
  navigateTo: string;
  icon: typeof IconBrain;
}

function buildChecklist(data: Record<string, unknown>): ChecklistItem[] {
  return [
    {
      key: 'ai_provider',
      label: 'Configure an AI Provider',
      description: 'Add at least one AI provider (e.g. Ollama, OpenAI) to power agent workflows.',
      completed: Boolean(data.has_ai_provider),
      navigateTo: '/ai-providers',
      icon: IconBrain,
    },
    {
      key: 'repo',
      label: 'Register a Repository',
      description: 'Connect a GitHub repository so agents can read and write code.',
      completed: Boolean(data.has_repo),
      navigateTo: '/repositories',
      icon: IconFolder,
    },
    {
      key: 'chat',
      label: 'Connect a Chat Channel',
      description: 'Link Slack or another channel to trigger workflows from conversations.',
      completed: Boolean(data.has_chat),
      navigateTo: '/settings/channels',
      icon: IconMessageCircle,
    },
  ];
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useOnboardingGetOnboardingStatus();

  if (isLoading) {
    return (
      <Center h={300}>
        <Loader />
      </Center>
    );
  }

  const payload = (data as { data: Record<string, unknown> } | undefined)?.data ?? {};
  const checklist = buildChecklist(payload);
  const completedCount = checklist.filter((item) => item.completed).length;
  const percentage = Math.round((completedCount / checklist.length) * 100);

  return (
    <Stack gap="lg">
      <Title order={2}>Setup Checklist</Title>

      <Paper p="md" radius="md" withBorder>
        <Group justify="space-between" mb="xs">
          <Text fw={600}>Completion</Text>
          <Text size="sm" c="dimmed">
            {completedCount} / {checklist.length} steps
          </Text>
        </Group>
        <Progress value={percentage} size="lg" radius="xl" color={percentage === 100 ? 'green' : 'indigo'} />
        <Text size="sm" ta="center" mt="xs" c="dimmed">
          {percentage}%
        </Text>
      </Paper>

      <Stack gap="sm">
        {checklist.map((item) => (
          <Paper key={item.key} p="md" radius="md" withBorder>
            <Group justify="space-between" wrap="nowrap">
              <Group gap="md" wrap="nowrap">
                <ThemeIcon
                  variant={item.completed ? 'filled' : 'light'}
                  color={item.completed ? 'green' : 'gray'}
                  size="lg"
                  radius="xl"
                >
                  {item.completed ? <IconCheck size={18} /> : <IconCircle size={18} />}
                </ThemeIcon>
                <div>
                  <Text fw={500}>{item.label}</Text>
                  <Text size="sm" c="dimmed">{item.description}</Text>
                </div>
              </Group>
              {!item.completed && (
                <Button
                  variant="light"
                  size="xs"
                  leftSection={<item.icon size={14} />}
                  onClick={() => void navigate(item.navigateTo)}
                >
                  Set up
                </Button>
              )}
            </Group>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}

export const Component = OnboardingPage;
