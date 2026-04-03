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

// --- Channel Connection CRUD (project-scoped linking) ---

export interface ChannelConnectionDetail {
  id: string;
  provider: string;
  channel_id: string;
  workspace_id: string;
  config: Record<string, unknown>;
  allowed_workflows: string[];
  project_ids: string[];
  created_at: string;
  updated_at: string;
}

export async function listChannelConnectionDetails(): Promise<ChannelConnectionDetail[]> {
  const { data } = await customInstance<{ data: ChannelConnectionDetail[] }>(
    '/api/v1/channel-connections',
  );
  return data ?? [];
}

export async function updateChannelConnection(
  connectionId: string,
  body: { project_ids?: string[]; allowed_workflows?: string[] },
): Promise<ChannelConnectionDetail> {
  const { data } = await customInstance<{ data: ChannelConnectionDetail }>(
    `/api/v1/channel-connections/${connectionId}`,
    { method: 'PATCH', body: JSON.stringify(body) },
  );
  return data!;
}
