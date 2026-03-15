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
  const { data } = await customInstance<ChannelConnection[]>({
    url: '/api/v1/settings/channels',
    method: 'GET',
  });
  return data ?? [];
}

export async function connectTelegram(
  body: TelegramConnectionRequest,
): Promise<ChannelConnection> {
  const { data } = await customInstance<ChannelConnection>({
    url: '/api/v1/settings/channels/telegram',
    method: 'POST',
    data: body,
  });
  return data!;
}

export async function getTelegramStatus(): Promise<ChannelStatus> {
  const { data } = await customInstance<ChannelStatus>({
    url: '/api/v1/settings/channels/telegram/status',
    method: 'GET',
  });
  return data!;
}

export async function disconnectTelegram(): Promise<void> {
  await customInstance<void>({
    url: '/api/v1/settings/channels/telegram',
    method: 'DELETE',
  });
}
