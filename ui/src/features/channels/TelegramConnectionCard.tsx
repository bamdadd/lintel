import { useState } from 'react';
import {
  Card,
  Title,
  Text,
  TextInput,
  Button,
  Group,
  Stack,
  Badge,
  Alert,
} from '@mantine/core';
import {
  connectTelegram,
  getTelegramStatus,
  disconnectTelegram,
} from './channelsApi';
import type { ChannelConnection } from './channelsApi';

interface Props {
  connection: ChannelConnection;
  onUpdate: () => void;
}

export function TelegramConnectionCard({ connection, onUpdate }: Props) {
  const [botToken, setBotToken] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    setSaving(true);
    setError(null);
    try {
      await connectTelegram({ bot_token: botToken, webhook_secret: webhookSecret });
      setBotToken('');
      setWebhookSecret('');
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
      const status = await getTelegramStatus();
      setTestResult(
        status.connected
          ? `Connected as @${status.bot_username}`
          : status.message,
      );
    } catch (err) {
      setTestResult(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectTelegram();
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect');
    }
  };

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={4}>Telegram</Title>
          <Badge
            color={connection.connected ? 'green' : 'gray'}
            variant="dot"
          >
            {connection.connected ? 'Connected' : 'Disconnected'}
          </Badge>
        </Group>

        {connection.connected && connection.bot_username && (
          <Text size="sm" c="dimmed">
            Bot: @{connection.bot_username}
          </Text>
        )}

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
              description="Get this from @BotFather on Telegram"
              placeholder="123456:ABC-DEF..."
              value={botToken}
              onChange={(e) => setBotToken(e.currentTarget.value)}
              type="password"
            />
            <TextInput
              label="Webhook Secret"
              description="Optional secret for webhook verification"
              placeholder="your-secret-token"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.currentTarget.value)}
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
