import { useEffect, useState } from 'react';
import {
  Container,
  Stepper,
  Button,
  Group,
  Title,
  Text,
  TextInput,
  Select,
  PasswordInput,
  Paper,
  Stack,
  Alert,
  Badge,
  ThemeIcon,
  Center,
  Loader,
} from '@mantine/core';
import {
  IconBrain,
  IconFolder,
  IconMessageCircle,
  IconRocket,
  IconCheck,
  IconAlertCircle,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router';
import { notifications } from '@mantine/notifications';

const API = '/api/v1';

async function apiPost(url: string, body: object) {
  const res = await fetch(`${API}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json();
}

type StepStatus = 'pending' | 'saving' | 'done' | 'error';

export function Component() {
  const navigate = useNavigate();
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(true);

  // Step 1: AI Provider
  const [providerType, setProviderType] = useState<string>('anthropic');
  const [providerName, setProviderName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiBase, setApiBase] = useState('');
  const [providerStatus, setProviderStatus] = useState<StepStatus>('pending');
  const [providerError, setProviderError] = useState('');

  // Step 2: Repository
  const [repoName, setRepoName] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [repoBranch, setRepoBranch] = useState('main');
  const [githubToken, setGithubToken] = useState('');
  const [repoStatus, setRepoStatus] = useState<StepStatus>('pending');
  const [repoError, setRepoError] = useState('');
  const [repoId, setRepoId] = useState('');

  // Step 3: Chat (optional)
  const [slackToken, setSlackToken] = useState('');
  const [chatStatus, setChatStatus] = useState<StepStatus>('pending');
  const [chatError, setChatError] = useState('');

  // Fetch onboarding status and skip completed steps
  useEffect(() => {
    fetch(`${API}/onboarding/status`)
      .then((res) => res.json())
      .then((status: { has_ai_provider: boolean; has_repo: boolean; has_chat: boolean; is_complete: boolean }) => {
        if (status.is_complete) {
          // Everything required is done — jump to finish
          if (status.has_ai_provider) setProviderStatus('done');
          if (status.has_repo) setRepoStatus('done');
          if (status.has_chat) setChatStatus('done');
          setActive(3);
        } else {
          // Find the first incomplete required step
          if (status.has_ai_provider) setProviderStatus('done');
          if (status.has_repo) setRepoStatus('done');
          if (status.has_chat) setChatStatus('done');

          if (!status.has_ai_provider) setActive(0);
          else if (!status.has_repo) setActive(1);
          else setActive(2);
        }
      })
      .catch(() => {
        // If the endpoint fails, start from the beginning
        setActive(0);
      })
      .finally(() => setLoading(false));
  }, []);

  const needsApiKey = !['ollama', 'bedrock'].includes(providerType);
  const needsApiBase = ['ollama', 'azure_openai', 'custom'].includes(providerType);

  async function saveProvider() {
    setProviderStatus('saving');
    setProviderError('');
    try {
      const body: Record<string, unknown> = {
        provider_type: providerType,
        name: providerName || `${providerType} provider`,
        is_default: true,
      };
      if (needsApiKey) body.api_key = apiKey;
      if (needsApiBase || apiBase) body.api_base = apiBase;
      await apiPost('/ai-providers', body);
      setProviderStatus('done');
      setActive(1);
    } catch (e) {
      setProviderError((e as Error).message);
      setProviderStatus('error');
    }
  }

  async function saveRepo() {
    setRepoStatus('saving');
    setRepoError('');
    try {
      if (githubToken) {
        await apiPost('/credentials', {
          credential_type: 'github_token',
          name: `${repoName || 'repo'} token`,
          secret: githubToken,
        });
      }
      const repo = await apiPost('/repositories', {
        name: repoName,
        url: repoUrl,
        default_branch: repoBranch,
        provider: 'github',
      });
      setRepoId(repo.repo_id ?? '');
      setRepoStatus('done');
      setActive(2);
    } catch (e) {
      setRepoError((e as Error).message);
      setRepoStatus('error');
    }
  }

  async function saveChat() {
    if (!slackToken) {
      setActive(3);
      return;
    }
    setChatStatus('saving');
    setChatError('');
    try {
      await apiPost('/settings/connections', {
        connection_id: 'slack-default',
        connection_type: 'slack',
        name: 'Slack',
        config: { bot_token: slackToken },
      });
      setChatStatus('done');
      setActive(3);
    } catch (e) {
      setChatError((e as Error).message);
      setChatStatus('error');
    }
  }

  function finish() {
    notifications.show({
      title: 'Setup complete',
      message: 'Your Lintel workspace is ready.',
      color: 'green',
      icon: <IconCheck size={16} />,
    });
    void navigate('/');
  }

  if (loading) {
    return (
      <Container size="sm" py="xl">
        <Center>
          <Loader />
        </Center>
      </Container>
    );
  }

  return (
    <Container size="sm" py="xl">
      <Stack gap="xl">
        <Center>
          <Stack align="center" gap={4}>
            <Title order={2}>Welcome to Lintel</Title>
            <Text c="dimmed">Let's get your workspace set up in a few steps.</Text>
          </Stack>
        </Center>

        <Stepper
          active={active}
          onStepClick={setActive}
          allowNextStepsSelect={false}
          styles={{
            steps: { display: 'flex', flexWrap: 'nowrap' },
            step: { flex: '1 1 0', minWidth: 0 },
          }}
        >
          {/* Step 1: AI Provider */}
          <Stepper.Step
            label="AI Provider"
            description="Connect an LLM"
            icon={<IconBrain size={18} />}
            completedIcon={<IconCheck size={18} />}
          >
            <Paper withBorder p="lg" mt="md">
              <Stack gap="md">
                <Select
                  label="Provider type"
                  data={[
                    { value: 'anthropic', label: 'Anthropic' },
                    { value: 'openai', label: 'OpenAI' },
                    { value: 'azure_openai', label: 'Azure OpenAI' },
                    { value: 'google', label: 'Google' },
                    { value: 'ollama', label: 'Ollama (local)' },
                    { value: 'bedrock', label: 'AWS Bedrock' },
                    { value: 'custom', label: 'Custom' },
                  ]}
                  value={providerType}
                  onChange={(v) => v && setProviderType(v)}
                />
                <TextInput
                  label="Display name"
                  placeholder={`My ${providerType} provider`}
                  value={providerName}
                  onChange={(e) => setProviderName(e.currentTarget.value)}
                />
                {needsApiKey && (
                  <PasswordInput
                    label="API Key"
                    placeholder="sk-..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.currentTarget.value)}
                    required
                  />
                )}
                {needsApiBase && (
                  <TextInput
                    label="API Base URL"
                    placeholder={
                      providerType === 'ollama'
                        ? 'http://localhost:11434'
                        : 'https://...'
                    }
                    value={apiBase}
                    onChange={(e) => setApiBase(e.currentTarget.value)}
                    required
                  />
                )}
                {providerError && (
                  <Alert
                    color="red"
                    icon={<IconAlertCircle size={16} />}
                    title="Error"
                  >
                    {providerError}
                  </Alert>
                )}
                <Group justify="flex-end">
                  <Button
                    onClick={saveProvider}
                    loading={providerStatus === 'saving'}
                    disabled={
                      (needsApiKey && !apiKey) ||
                      (needsApiBase && !apiBase)
                    }
                  >
                    Save & Continue
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>

          {/* Step 2: Repository */}
          <Stepper.Step
            label="Repository"
            description="Connect a Git repo"
            icon={<IconFolder size={18} />}
            completedIcon={<IconCheck size={18} />}
          >
            <Paper withBorder p="lg" mt="md">
              <Stack gap="md">
                <TextInput
                  label="Repository name"
                  placeholder="my-app"
                  value={repoName}
                  onChange={(e) => setRepoName(e.currentTarget.value)}
                  required
                />
                <TextInput
                  label="Repository URL"
                  placeholder="https://github.com/owner/repo.git"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.currentTarget.value)}
                  required
                />
                <TextInput
                  label="Default branch"
                  value={repoBranch}
                  onChange={(e) => setRepoBranch(e.currentTarget.value)}
                />
                <PasswordInput
                  label="GitHub token"
                  description="Personal access token or fine-grained token with repo access"
                  placeholder="ghp_..."
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.currentTarget.value)}
                />
                {repoError && (
                  <Alert
                    color="red"
                    icon={<IconAlertCircle size={16} />}
                    title="Error"
                  >
                    {repoError}
                  </Alert>
                )}
                <Group justify="space-between">
                  <Button variant="default" onClick={() => setActive(0)}>
                    Back
                  </Button>
                  <Button
                    onClick={saveRepo}
                    loading={repoStatus === 'saving'}
                    disabled={!repoName || !repoUrl}
                  >
                    Save & Continue
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>

          {/* Step 3: Chat (optional) */}
          <Stepper.Step
            label="Chat"
            description="Optional: connect Slack"
            icon={<IconMessageCircle size={18} />}
            completedIcon={<IconCheck size={18} />}
          >
            <Paper withBorder p="lg" mt="md">
              <Stack gap="md">
                <Alert color="blue" variant="light">
                  This step is optional. You can use the built-in chat without
                  Slack, or add Slack later from Settings.
                </Alert>
                <PasswordInput
                  label="Slack Bot Token"
                  placeholder="xoxb-..."
                  value={slackToken}
                  onChange={(e) => setSlackToken(e.currentTarget.value)}
                />
                {chatError && (
                  <Alert
                    color="red"
                    icon={<IconAlertCircle size={16} />}
                    title="Error"
                  >
                    {chatError}
                  </Alert>
                )}
                <Group justify="space-between">
                  <Button variant="default" onClick={() => setActive(1)}>
                    Back
                  </Button>
                  <Button
                    onClick={saveChat}
                    loading={chatStatus === 'saving'}
                  >
                    {slackToken ? 'Save & Continue' : 'Skip & Continue'}
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>

          {/* Step 4: Finish */}
          <Stepper.Step
            label="Ready"
            description="Start using Lintel"
            icon={<IconRocket size={18} />}
            completedIcon={<IconCheck size={18} />}
          >
            <Paper withBorder p="lg" mt="md">
              <Stack gap="md" align="center">
                <ThemeIcon size={64} radius="xl" color="green" variant="light">
                  <IconCheck size={32} />
                </ThemeIcon>
                <Title order={3}>You're all set!</Title>
                <Text c="dimmed" ta="center">
                  Your workspace is configured. Here's what's ready:
                </Text>
                <Group>
                  <Badge color="green" variant="light" size="lg">
                    AI Provider
                  </Badge>
                  <Badge color="green" variant="light" size="lg">
                    Repository
                  </Badge>
                  {chatStatus === 'done' ? (
                    <Badge color="green" variant="light" size="lg">
                      Slack
                    </Badge>
                  ) : (
                    <Badge color="gray" variant="light" size="lg">
                      Slack (skipped)
                    </Badge>
                  )}
                </Group>
                <Text c="dimmed" size="sm" ta="center">
                  Head to the Chat page to submit your first task, or explore
                  Workflows to set up automated pipelines.
                </Text>
                <Group>
                  <Button variant="default" onClick={() => setActive(2)}>
                    Back
                  </Button>
                  <Button onClick={finish} size="md">
                    Go to Dashboard
                  </Button>
                </Group>
              </Stack>
            </Paper>
          </Stepper.Step>
        </Stepper>
      </Stack>
    </Container>
  );
}
