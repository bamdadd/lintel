import { useState } from 'react';
import {
  Card,
  Title,
  TextInput,
  Button,
  Group,
  Stack,
  Badge,
  Alert,
} from '@mantine/core';
import {
  connectSlack,
  getSlackStatus,
  disconnectSlack,
} from './channelsApi';
import type { ChannelConnection } from './channelsApi';

interface Props {
  connection: ChannelConnection;
  onUpdate: () => void;
}

export function SlackConnectionCard({ connection, onUpdate }: Props) {
  const [botToken, setBotToken] = useState('');
  const [signingSecret, setSigningSecret] = useState('');
  const [appToken, setAppToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    setSaving(true);
    setError(null);
    try {
      await connectSlack({
        bot_token: botToken,
        signing_secret: signingSecret,
        app_token: appToken,
      });
      setBotToken('');
      setSigningSecret('');
      setAppToken('');
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const status = await getSlackStatus();
      setTestResult(status.connected ? 'Connection configured' : status.message);
    } catch (err) {
      setTestResult(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectSlack();
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect');
    }
  };

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={4}>Slack</Title>
          <Badge
            color={connection.connected ? 'green' : 'gray'}
            variant="dot"
          >
            {connection.connected ? 'Connected' : 'Disconnected'}
          </Badge>
        </Group>

        {error && (
          <Alert color="red" title="Error">
            {error}
          </Alert>
        )}

        {testResult && (
          <Alert color="blue" title="Test Result">
            {testResult}
          </Alert>
        )}

        {!connection.connected && (
          <>
            <TextInput
              label="Bot Token"
              description="Bot User OAuth Token (xoxb-...)"
              placeholder="xoxb-..."
              value={botToken}
              onChange={(e) => setBotToken(e.currentTarget.value)}
              type="password"
            />
            <TextInput
              label="Signing Secret"
              description="Found in your Slack app's Basic Information page"
              placeholder="your-signing-secret"
              value={signingSecret}
              onChange={(e) => setSigningSecret(e.currentTarget.value)}
              type="password"
            />
            <TextInput
              label="App Token"
              description="App-Level Token for Socket Mode (xapp-...)"
              placeholder="xapp-..."
              value={appToken}
              onChange={(e) => setAppToken(e.currentTarget.value)}
              type="password"
            />
            <Button
              onClick={handleConnect}
              loading={saving}
              disabled={!botToken}
            >
              Save & Connect
            </Button>
          </>
        )}

        {connection.connected && (
          <Group>
            <Button
              variant="outline"
              onClick={handleTest}
              loading={testing}
            >
              Test Connection
            </Button>
            <Button
              variant="outline"
              color="red"
              onClick={handleDisconnect}
            >
              Disconnect
            </Button>
          </Group>
        )}
      </Stack>
    </Card>
  );
}
