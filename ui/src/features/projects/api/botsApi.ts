import { customInstance } from '@/shared/api/client';

export interface Bot {
  bot_id: string;
  name: string;
  platform: string;
  scopes: string[];
  status: string;
}

export interface BotScopeEntry {
  resource_type: 'project' | 'workflow' | 'agent';
  resource_id: string;
}

export async function listBots(): Promise<Bot[]> {
  const data = await customInstance<Bot[]>('/api/v1/bots');
  return data ?? [];
}

export async function createBot(body: {
  name: string;
  platform: string;
  scopes?: string[];
}): Promise<Bot> {
  const data = await customInstance<Bot>('/api/v1/bots', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return data!;
}

export async function createBotScope(body: {
  bot_id: string;
  resource_type: string;
  resource_id: string;
}): Promise<void> {
  await customInstance<unknown>('/api/v1/bot-scopes', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getBotScopes(botId: string): Promise<{
  bot_id: string;
  scopes: BotScopeEntry[];
}> {
  const data = await customInstance<{ bot_id: string; scopes: BotScopeEntry[] }>(
    `/api/v1/bot-scopes/${botId}`,
  );
  return data!;
}
