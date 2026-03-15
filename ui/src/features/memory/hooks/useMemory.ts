import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

// Types
interface MemoryFact {
  id: string;
  project_id: string;
  memory_type: string;
  fact_type: string;
  content: string;
  embedding_id: string | null;
  source_workflow_id: string | null;
  created_at: string;
  updated_at: string;
}

interface MemoryListResponse {
  items: MemoryFact[];
  total: number;
  page: number;
  page_size: number;
}

interface MemoryChunk {
  id: string;
  project_id: string;
  memory_type: string;
  fact_type: string;
  content: string;
  score: number;
  rank: number;
  source_workflow_id: string | null;
  created_at: string;
}

interface MemorySearchResponse {
  query: string;
  results: MemoryChunk[];
  total: number;
}

export function useMemoryList(params: {
  project_id?: string;
  memory_type?: string;
  page?: number;
  page_size?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params.project_id) searchParams.set('project_id', params.project_id);
  if (params.memory_type) searchParams.set('memory_type', params.memory_type);
  searchParams.set('page', String(params.page ?? 1));
  searchParams.set('page_size', String(params.page_size ?? 20));

  return useQuery({
    queryKey: ['/api/v1/memory', params],
    queryFn: () => customInstance<{ data: MemoryListResponse }>(`/api/v1/memory?${searchParams.toString()}`),
    enabled: !!params.project_id,
  });
}

export function useMemoryDetail(memoryId: string | undefined) {
  return useQuery({
    queryKey: ['/api/v1/memory', memoryId],
    queryFn: () => customInstance<{ data: MemoryFact }>(`/api/v1/memory/${memoryId}`),
    enabled: !!memoryId,
  });
}

export function useMemorySearch(params: {
  q: string;
  project_id?: string;
  memory_type?: string;
  top_k?: number;
}) {
  const searchParams = new URLSearchParams();
  searchParams.set('q', params.q);
  if (params.project_id) searchParams.set('project_id', params.project_id);
  if (params.memory_type) searchParams.set('memory_type', params.memory_type);
  if (params.top_k) searchParams.set('top_k', String(params.top_k));

  return useQuery({
    queryKey: ['/api/v1/memory/search', params],
    queryFn: () => customInstance<{ data: MemorySearchResponse }>(`/api/v1/memory/search?${searchParams.toString()}`),
    enabled: params.q.length >= 2 && !!params.project_id,
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) =>
      customInstance(`/api/v1/memory/${memoryId}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['/api/v1/memory'] });
    },
  });
}

export function useCreateMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { project_id: string; content: string; memory_type: string; fact_type: string }) =>
      customInstance<{ data: MemoryFact }>('/api/v1/memory', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['/api/v1/memory'] });
    },
  });
}

export type { MemoryFact, MemoryChunk, MemoryListResponse, MemorySearchResponse };
