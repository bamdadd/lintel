import { useQuery } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import type {
  ProcessFlowMap,
  FlowEntry,
  FlowDiagram,
  FlowMetrics,
} from '../types';

const BASE = '/api/v1/flow-maps';

export const processMiningKeys = {
  all: ['process-mining'] as const,
  lists: () => [...processMiningKeys.all, 'list'] as const,
  list: (repositoryId?: string) =>
    [...processMiningKeys.lists(), { repositoryId }] as const,
  detail: (mapId: string) => [...processMiningKeys.all, 'detail', mapId] as const,
  flows: (mapId: string, flowType?: string) =>
    [...processMiningKeys.all, 'flows', mapId, { flowType }] as const,
  diagrams: (mapId: string, flowType?: string) =>
    [...processMiningKeys.all, 'diagrams', mapId, { flowType }] as const,
  metrics: (mapId: string) =>
    [...processMiningKeys.all, 'metrics', mapId] as const,
};

export function useListFlowMaps(repositoryId?: string) {
  const params = repositoryId ? `?repository_id=${repositoryId}` : '';
  return useQuery({
    queryKey: processMiningKeys.list(repositoryId),
    queryFn: () =>
      customInstance<{ data: ProcessFlowMap[]; status: number; headers: Headers }>(
        `${BASE}${params}`,
        { method: 'GET' },
      ).then((r) => r.data),
  });
}

export function useGetFlowMap(mapId: string) {
  return useQuery({
    queryKey: processMiningKeys.detail(mapId),
    queryFn: () =>
      customInstance<{ data: ProcessFlowMap; status: number; headers: Headers }>(
        `${BASE}/${mapId}`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetFlows(mapId: string, flowType?: string) {
  const params = flowType ? `?flow_type=${flowType}` : '';
  return useQuery({
    queryKey: processMiningKeys.flows(mapId, flowType),
    queryFn: () =>
      customInstance<{ data: FlowEntry[]; status: number; headers: Headers }>(
        `${BASE}/${mapId}/flows${params}`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetDiagrams(mapId: string, flowType?: string) {
  const params = flowType ? `?flow_type=${flowType}` : '';
  return useQuery({
    queryKey: processMiningKeys.diagrams(mapId, flowType),
    queryFn: () =>
      customInstance<{ data: FlowDiagram[]; status: number; headers: Headers }>(
        `${BASE}/${mapId}/diagrams${params}`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}

export function useGetFlowMetrics(mapId: string) {
  return useQuery({
    queryKey: processMiningKeys.metrics(mapId),
    queryFn: () =>
      customInstance<{ data: FlowMetrics; status: number; headers: Headers }>(
        `${BASE}/${mapId}/metrics`,
        { method: 'GET' },
      ).then((r) => r.data),
    enabled: !!mapId,
  });
}
