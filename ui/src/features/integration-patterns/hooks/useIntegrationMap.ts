import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import type {
  IntegrationMap,
  GraphData,
  PatternCatalogueEntry,
  AntipatternDetection,
  ServiceCouplingScore,
} from '../types';

const BASE = '/api/v1/integration-maps';

// ── Query keys ──────────────────────────────────────────────────────────────

export const integrationMapKeys = {
  all: ['integration-maps'] as const,
  lists: () => [...integrationMapKeys.all, 'list'] as const,
  list: (repositoryId?: string) =>
    [...integrationMapKeys.lists(), { repositoryId }] as const,
  detail: (mapId: string) => [...integrationMapKeys.all, 'detail', mapId] as const,
  graph: (mapId: string) => [...integrationMapKeys.all, 'graph', mapId] as const,
  patterns: (mapId: string) => [...integrationMapKeys.all, 'patterns', mapId] as const,
  antipatterns: (mapId: string) =>
    [...integrationMapKeys.all, 'antipatterns', mapId] as const,
  coupling: (mapId: string) => [...integrationMapKeys.all, 'coupling', mapId] as const,
};

// ── Hooks ───────────────────────────────────────────────────────────────────

export function useListIntegrationMaps(repositoryId?: string) {
  const params = repositoryId ? `?repository_id=${repositoryId}` : '';
  return useQuery({
    queryKey: integrationMapKeys.list(repositoryId),
    queryFn: () =>
      customInstance<{ data: IntegrationMap[]; status: number; headers: Headers }>(
        `${BASE}${params}`,
        { method: 'GET' },
      ).then((r) => r.data),
  });
}

export function useGetIntegrationMap(mapId: string) {
  return useQuery({
    queryKey: integrationMapKeys.detail(mapId),
    queryFn: () =>
      customInstance<{ data: IntegrationMap; status: number; headers: Headers }>(
        `${BASE}/${mapId}`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetIntegrationMapGraph(mapId: string) {
  return useQuery({
    queryKey: integrationMapKeys.graph(mapId),
    queryFn: () =>
      customInstance<{ data: GraphData; status: number; headers: Headers }>(
        `${BASE}/${mapId}/graph`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetIntegrationMapPatterns(mapId: string) {
  return useQuery({
    queryKey: integrationMapKeys.patterns(mapId),
    queryFn: () =>
      customInstance<{
        data: PatternCatalogueEntry[];
        status: number;
        headers: Headers;
      }>(`${BASE}/${mapId}/patterns`, { method: 'GET' }).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetIntegrationMapAntipatterns(mapId: string) {
  return useQuery({
    queryKey: integrationMapKeys.antipatterns(mapId),
    queryFn: () =>
      customInstance<{
        data: AntipatternDetection[];
        status: number;
        headers: Headers;
      }>(`${BASE}/${mapId}/antipatterns`, { method: 'GET' }).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetIntegrationMapCouplingScores(mapId: string) {
  return useQuery({
    queryKey: integrationMapKeys.coupling(mapId),
    queryFn: () =>
      customInstance<{
        data: ServiceCouplingScore[];
        status: number;
        headers: Headers;
      }>(`${BASE}/${mapId}/coupling-scores`, { method: 'GET' }).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useCreateIntegrationMap() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { repository_id: string }) =>
      customInstance<{ data: IntegrationMap; status: number; headers: Headers }>(
        BASE,
        { method: 'POST', body: JSON.stringify(body) },
      ).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: integrationMapKeys.lists() });
    },
  });
}
