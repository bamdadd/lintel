/**
 * Hand-written API client for /api/v1/models endpoints.
 * Matches orval-generated patterns (react-query hooks + customInstance).
 */
import { useMutation, useQuery } from '@tanstack/react-query';
import type {
  QueryClient,
  UseMutationOptions,
  UseMutationResult,
  UseQueryOptions,
  UseQueryResult,
} from '@tanstack/react-query';

import { customInstance } from '../../../shared/api/client';

// --- Types ---

export interface ModelItem {
  model_id: string;
  provider_id: string;
  name: string;
  model_name: string;
  max_tokens: number;
  temperature: number;
  is_default: boolean;
  capabilities: string[];
  config: Record<string, unknown> | null;
  provider_name: string;
  provider_type: string;
}

export interface CreateModelRequest {
  model_id?: string;
  provider_id: string;
  name: string;
  model_name: string;
  max_tokens?: number;
  temperature?: number;
  is_default?: boolean;
  capabilities?: string[];
  config?: Record<string, unknown>;
}

export interface UpdateModelRequest {
  name?: string;
  model_name?: string;
  max_tokens?: number;
  temperature?: number;
  is_default?: boolean;
  capabilities?: string[];
  config?: Record<string, unknown>;
}

export interface ModelAssignmentItem {
  assignment_id: string;
  model_id: string;
  context: string;
  context_id: string;
  priority: number;
}

export interface CreateModelAssignmentRequest {
  assignment_id?: string;
  context: string;
  context_id: string;
  priority?: number;
}

export interface AvailableModel {
  model_name: string;
  display_name: string;
  family: string;
  parameter_size: string;
  quantization_level: string;
  format: string;
  size_bytes: number;
  max_tokens: number;
  temperature: number;
}

// --- Fetchers ---

const listAvailableModels = async (
  providerId: string,
  options?: RequestInit,
): Promise<Wrapped<AvailableModel[]>> =>
  customInstance<Wrapped<AvailableModel[]>>(
    `/api/v1/ai-providers/${providerId}/available-models`,
    { ...options, method: 'GET' },
  );

type Wrapped<T> = { data: T; status: number; headers: Headers };

const listModels = async (
  providerId?: string,
  options?: RequestInit,
): Promise<Wrapped<ModelItem[]>> =>
  customInstance<Wrapped<ModelItem[]>>(
    `/api/v1/models${providerId ? `?provider_id=${providerId}` : ''}`,
    { ...options, method: 'GET' },
  );

const getModel = async (
  modelId: string,
  options?: RequestInit,
): Promise<Wrapped<ModelItem>> =>
  customInstance<Wrapped<ModelItem>>(`/api/v1/models/${modelId}`, {
    ...options,
    method: 'GET',
  });

const createModel = async (
  data: CreateModelRequest,
  options?: RequestInit,
): Promise<Wrapped<ModelItem>> =>
  customInstance<Wrapped<ModelItem>>('/api/v1/models', {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    body: JSON.stringify(data),
  });

const updateModel = async (
  modelId: string,
  data: UpdateModelRequest,
  options?: RequestInit,
): Promise<Wrapped<ModelItem>> =>
  customInstance<Wrapped<ModelItem>>(`/api/v1/models/${modelId}`, {
    ...options,
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    body: JSON.stringify(data),
  });

const deleteModel = async (
  modelId: string,
  options?: RequestInit,
): Promise<Wrapped<void>> =>
  customInstance<Wrapped<void>>(`/api/v1/models/${modelId}`, {
    ...options,
    method: 'DELETE',
  });

const listModelAssignments = async (
  modelId: string,
  options?: RequestInit,
): Promise<Wrapped<ModelAssignmentItem[]>> =>
  customInstance<Wrapped<ModelAssignmentItem[]>>(
    `/api/v1/models/${modelId}/assignments`,
    { ...options, method: 'GET' },
  );

const createModelAssignment = async (
  modelId: string,
  data: CreateModelAssignmentRequest,
  options?: RequestInit,
): Promise<Wrapped<ModelAssignmentItem>> =>
  customInstance<Wrapped<ModelAssignmentItem>>(
    `/api/v1/models/${modelId}/assignments`,
    {
      ...options,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      body: JSON.stringify(data),
    },
  );

const listAllAssignments = async (
  context?: string,
  contextId?: string,
  options?: RequestInit,
): Promise<Wrapped<ModelAssignmentItem[]>> => {
  const params = new URLSearchParams();
  if (context) params.set('context', context);
  if (contextId) params.set('context_id', contextId);
  const qs = params.toString();
  return customInstance<Wrapped<ModelAssignmentItem[]>>(
    `/api/v1/model-assignments${qs ? `?${qs}` : ''}`,
    { ...options, method: 'GET' },
  );
};

const deleteAssignment = async (
  assignmentId: string,
  options?: RequestInit,
): Promise<Wrapped<void>> =>
  customInstance<Wrapped<void>>(
    `/api/v1/model-assignments/${assignmentId}`,
    { ...options, method: 'DELETE' },
  );

// --- Query Hooks ---

export const useModelsListModels = <TData = Awaited<ReturnType<typeof listModels>>>(
  providerId?: string,
  options?: { query?: Partial<UseQueryOptions<Awaited<ReturnType<typeof listModels>>, unknown, TData>> },
  queryClient?: QueryClient,
): UseQueryResult<TData> => {
  const queryKey = ['/api/v1/models', providerId] as const;
  return useQuery(
    {
      queryKey,
      queryFn: ({ signal }) => listModels(providerId, { signal }),
      ...options?.query,
    } as UseQueryOptions<Awaited<ReturnType<typeof listModels>>, unknown, TData>,
    queryClient,
  );
};

export const useModelsGetModel = <TData = Awaited<ReturnType<typeof getModel>>>(
  modelId: string,
  options?: { query?: Partial<UseQueryOptions<Awaited<ReturnType<typeof getModel>>, unknown, TData>> },
  queryClient?: QueryClient,
): UseQueryResult<TData> => {
  const queryKey = [`/api/v1/models/${modelId}`] as const;
  return useQuery(
    {
      queryKey,
      queryFn: ({ signal }) => getModel(modelId, { signal }),
      enabled: !!modelId,
      ...options?.query,
    } as UseQueryOptions<Awaited<ReturnType<typeof getModel>>, unknown, TData>,
    queryClient,
  );
};

export const useModelsListModelAssignments = <TData = Awaited<ReturnType<typeof listModelAssignments>>>(
  modelId: string,
  options?: { query?: Partial<UseQueryOptions<Awaited<ReturnType<typeof listModelAssignments>>, unknown, TData>> },
  queryClient?: QueryClient,
): UseQueryResult<TData> => {
  const queryKey = [`/api/v1/models/${modelId}/assignments`] as const;
  return useQuery(
    {
      queryKey,
      queryFn: ({ signal }) => listModelAssignments(modelId, { signal }),
      enabled: !!modelId,
      ...options?.query,
    } as UseQueryOptions<Awaited<ReturnType<typeof listModelAssignments>>, unknown, TData>,
    queryClient,
  );
};

export const useModelsListAllAssignments = <TData = Awaited<ReturnType<typeof listAllAssignments>>>(
  context?: string,
  contextId?: string,
  options?: { query?: Partial<UseQueryOptions<Awaited<ReturnType<typeof listAllAssignments>>, unknown, TData>> },
  queryClient?: QueryClient,
): UseQueryResult<TData> => {
  const queryKey = ['/api/v1/model-assignments', context, contextId] as const;
  return useQuery(
    {
      queryKey,
      queryFn: ({ signal }) => listAllAssignments(context, contextId, { signal }),
      ...options?.query,
    } as UseQueryOptions<Awaited<ReturnType<typeof listAllAssignments>>, unknown, TData>,
    queryClient,
  );
};

export const useAvailableModels = <TData = Awaited<ReturnType<typeof listAvailableModels>>>(
  providerId: string,
  options?: { query?: Partial<UseQueryOptions<Awaited<ReturnType<typeof listAvailableModels>>, unknown, TData>> },
  queryClient?: QueryClient,
): UseQueryResult<TData> => {
  const queryKey = [`/api/v1/ai-providers/${providerId}/available-models`] as const;
  return useQuery(
    {
      queryKey,
      queryFn: ({ signal }) => listAvailableModels(providerId, { signal }),
      enabled: !!providerId,
      ...options?.query,
    } as UseQueryOptions<Awaited<ReturnType<typeof listAvailableModels>>, unknown, TData>,
    queryClient,
  );
};

// --- Mutation Hooks ---

export const useModelsCreateModel = (
  options?: { mutation?: UseMutationOptions<Awaited<ReturnType<typeof createModel>>, unknown, { data: CreateModelRequest }> },
  queryClient?: QueryClient,
): UseMutationResult<Awaited<ReturnType<typeof createModel>>, unknown, { data: CreateModelRequest }> =>
  useMutation(
    { mutationKey: ['modelsCreateModel'], mutationFn: ({ data }) => createModel(data), ...options?.mutation },
    queryClient,
  );

export const useModelsUpdateModel = (
  options?: { mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateModel>>, unknown, { modelId: string; data: UpdateModelRequest }> },
  queryClient?: QueryClient,
): UseMutationResult<Awaited<ReturnType<typeof updateModel>>, unknown, { modelId: string; data: UpdateModelRequest }> =>
  useMutation(
    { mutationKey: ['modelsUpdateModel'], mutationFn: ({ modelId, data }) => updateModel(modelId, data), ...options?.mutation },
    queryClient,
  );

export const useModelsDeleteModel = (
  options?: { mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteModel>>, unknown, { modelId: string }> },
  queryClient?: QueryClient,
): UseMutationResult<Awaited<ReturnType<typeof deleteModel>>, unknown, { modelId: string }> =>
  useMutation(
    { mutationKey: ['modelsDeleteModel'], mutationFn: ({ modelId }) => deleteModel(modelId), ...options?.mutation },
    queryClient,
  );

export const useModelsCreateAssignment = (
  options?: { mutation?: UseMutationOptions<Awaited<ReturnType<typeof createModelAssignment>>, unknown, { modelId: string; data: CreateModelAssignmentRequest }> },
  queryClient?: QueryClient,
): UseMutationResult<Awaited<ReturnType<typeof createModelAssignment>>, unknown, { modelId: string; data: CreateModelAssignmentRequest }> =>
  useMutation(
    { mutationKey: ['modelsCreateAssignment'], mutationFn: ({ modelId, data }) => createModelAssignment(modelId, data), ...options?.mutation },
    queryClient,
  );

export const useModelsDeleteAssignment = (
  options?: { mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteAssignment>>, unknown, { assignmentId: string }> },
  queryClient?: QueryClient,
): UseMutationResult<Awaited<ReturnType<typeof deleteAssignment>>, unknown, { assignmentId: string }> =>
  useMutation(
    { mutationKey: ['modelsDeleteAssignment'], mutationFn: ({ assignmentId }) => deleteAssignment(assignmentId), ...options?.mutation },
    queryClient,
  );
