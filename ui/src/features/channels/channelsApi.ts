import { customInstance } from '@/shared/api/client';

export interface ChannelConnection {
  channel_type: string;
  connected: boolean;
  bot_username: string;
}

export interface TelegramConnectionRequest {
  bot_token: string;
  webhook_secret?: string;
}

export interface ChannelStatus {
  channel_type: string;
  connected: boolean;
  bot_username: string;
  message: string;
}

export async function listChannelConnections(): Promise<ChannelConnection[]> {
  const { data } = await customInstance<{ data: ChannelConnection[] }>(
    '/api/v1/settings/channels',
  );
  return data ?? [];
}

export async function connectTelegram(
  body: TelegramConnectionRequest,
): Promise<ChannelConnection> {
  const { data } = await customInstance<{ data: ChannelConnection }>(
    '/api/v1/settings/channels/telegram',
    { method: 'POST', body: JSON.stringify(body) },
  );
  return data!;
}

export async function getTelegramStatus(): Promise<ChannelStatus> {
  const { data } = await customInstance<{ data: ChannelStatus }>(
    '/api/v1/settings/channels/telegram/status',
  );
  return data!;
}

export async function disconnectTelegram(): Promise<void> {
  await customInstance<void>(
    '/api/v1/settings/channels/telegram',
    { method: 'DELETE' },
  );
}

export interface SlackConnectionRequest {
  bot_token: string;
  signing_secret?: string;
  app_token?: string;
}

export async function connectSlack(
  body: SlackConnectionRequest,
): Promise<ChannelConnection> {
  const { data } = await customInstance<{ data: ChannelConnection }>(
    '/api/v1/settings/channels/slack',
    { method: 'POST', body: JSON.stringify(body) },
  );
  return data!;
}

export async function getSlackStatus(): Promise<ChannelStatus> {
  const { data } = await customInstance<{ data: ChannelStatus }>(
    '/api/v1/settings/channels/slack/status',
  );
  return data!;
}

export async function disconnectSlack(): Promise<void> {
  await customInstance<void>(
    '/api/v1/settings/channels/slack',
    { method: 'DELETE' },
  );
}
