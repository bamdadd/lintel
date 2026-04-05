import { customInstance } from '@/shared/api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SyncConfig {
  sync_config_id: string;
  board_id: string;
  provider: string;
  direction: string;
  conflict_strategy: string;
  connection_id: string;
  external_project_key: string;
  external_database_id: string;
  status: string;
  last_synced: string;
  items_in_sync: number;
}

export interface CreateSyncConfigPayload {
  board_id: string;
  provider: string;
  direction?: string;
  conflict_strategy?: string;
  connection_id?: string;
  external_project_key?: string;
  external_database_id?: string;
}

export interface UpdateSyncConfigPayload {
  direction?: string;
  conflict_strategy?: string;
  connection_id?: string;
  external_project_key?: string;
  external_database_id?: string;
}

export interface TriggerSyncResult {
  pulled: number;
  pushed: number;
  status: string;
}

export interface NotionConnectPayload {
  project_id: string;
  database_id: string;
  api_key: string;
}

// ---------------------------------------------------------------------------
// Board Sync Config API
// ---------------------------------------------------------------------------

export async function listSyncConfigs(boardId?: string): Promise<SyncConfig[]> {
  const qs = boardId ? `?board_id=${encodeURIComponent(boardId)}` : '';
  const { data } = await customInstance<{ data: SyncConfig[] }>(
    `/api/v1/board-sync/configs${qs}`,
  );
  return data ?? [];
}

export async function createSyncConfig(
  payload: CreateSyncConfigPayload,
): Promise<SyncConfig> {
  const { data } = await customInstance<{ data: SyncConfig }>(
    '/api/v1/board-sync/configs',
    { method: 'POST', body: JSON.stringify(payload) },
  );
  return data!;
}

export async function updateSyncConfig(
  syncConfigId: string,
  payload: UpdateSyncConfigPayload,
): Promise<SyncConfig> {
  const { data } = await customInstance<{ data: SyncConfig }>(
    `/api/v1/board-sync/configs/${syncConfigId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  );
  return data!;
}

export async function deleteSyncConfig(syncConfigId: string): Promise<void> {
  await customInstance<void>(
    `/api/v1/board-sync/configs/${syncConfigId}`,
    { method: 'DELETE' },
  );
}

export async function triggerSync(syncConfigId: string): Promise<TriggerSyncResult> {
  const { data } = await customInstance<{ data: TriggerSyncResult }>(
    `/api/v1/board-sync/configs/${syncConfigId}/sync`,
    { method: 'POST' },
  );
  return data!;
}

// ---------------------------------------------------------------------------
// Notion Connect API
// ---------------------------------------------------------------------------

export async function connectNotion(
  payload: NotionConnectPayload,
): Promise<Record<string, unknown>> {
  const { data } = await customInstance<{ data: Record<string, unknown> }>(
    '/api/v1/integrations/notion/connect',
    { method: 'POST', body: JSON.stringify(payload) },
  );
  return data!;
}
