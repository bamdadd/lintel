import { useQuery, useMutation } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

interface BoardColumn {
  column_id: string;
  name: string;
  position: number;
  work_item_status: string;
  wip_limit: number;
}

export interface Board {
  board_id: string;
  project_id: string;
  name: string;
  columns: BoardColumn[];
  auto_move: boolean;
}

export interface WorkItem {
  work_item_id: string;
  project_id: string;
  title: string;
  description: string;
  work_type: string;
  status: string;
  assignee_agent_role: string;
  thread_ref_str: string;
  branch_name: string;
  pr_url: string;
  tags: string[];
  column_id: string;
  column_position: number;
}

interface ListResponse<T> {
  data: T[];
  status: number;
  headers: Headers;
}

interface SingleResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

export function useBoardsListBoards(projectId?: string) {
  return useQuery({
    queryKey: ['/api/v1/boards', projectId],
    queryFn: () =>
      customInstance<ListResponse<Board>>(
        projectId
          ? `/api/v1/projects/${projectId}/boards`
          : '/api/v1/projects/_/boards',
      ),
    enabled: !!projectId,
  });
}

export function useBoardsGetBoard(boardId: string | undefined) {
  return useQuery({
    queryKey: ['/api/v1/boards', boardId],
    queryFn: () =>
      customInstance<SingleResponse<Board>>(`/api/v1/boards/${boardId}`),
    enabled: !!boardId,
  });
}

export function useWorkItemsForBoard(projectId?: string) {
  return useQuery({
    queryKey: ['/api/v1/work-items', { project_id: projectId }],
    queryFn: () =>
      customInstance<ListResponse<WorkItem>>(
        `/api/v1/work-items${projectId ? `?project_id=${projectId}` : ''}`,
      ),
  });
}

export function useUpdateBoard() {
  return useMutation({
    mutationFn: ({
      boardId,
      data,
    }: {
      boardId: string;
      data: Record<string, unknown>;
    }) =>
      customInstance<SingleResponse<Board>>(
        `/api/v1/boards/${boardId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(data),
        },
      ),
  });
}

export function useDeleteBoard() {
  return useMutation({
    mutationFn: (boardId: string) =>
      customInstance<undefined>(`/api/v1/boards/${boardId}`, { method: 'DELETE' }),
  });
}

export interface PipelineRun {
  run_id: string;
  project_id: string;
  work_item_id: string;
  workflow_definition_id: string;
  status: string;
  trigger_type: string;
  created_at: string;
}

export function usePipelinesForWorkItem(workItemId: string | undefined) {
  return useQuery({
    queryKey: ['/api/v1/pipelines', { work_item_id: workItemId }],
    queryFn: async () => {
      const resp = await customInstance<ListResponse<PipelineRun>>('/api/v1/pipelines');
      // Filter client-side since API doesn't support work_item_id filter
      const all = (resp?.data ?? resp) as unknown as PipelineRun[];
      const filtered = Array.isArray(all) ? all.filter((r) => r.work_item_id === workItemId) : [];
      return filtered.sort((a, b) =>
        new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime(),
      );
    },
    enabled: !!workItemId,
  });
}

export interface PipelineStage {
  stage_id: string;
  name: string;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
}

export function usePipelineStages(runId: string | undefined) {
  return useQuery({
    queryKey: ['/api/v1/pipelines', runId, 'stages'],
    queryFn: () =>
      customInstance<ListResponse<PipelineStage>>(
        `/api/v1/pipelines/${runId}/stages`,
      ),
    enabled: !!runId,
  });
}

/**
 * Fetches the latest pipeline + its stages for a work item.
 * Used by WorkItemCard to show stage indicator boxes.
 */
export function useLatestPipelineWithStages(workItemId: string | undefined) {
  const { data: pipelines } = usePipelinesForWorkItem(workItemId);
  const latestPipeline = pipelines?.[0];
  const { data: stagesResp } = usePipelineStages(latestPipeline?.run_id);
  const stages = (stagesResp?.data ?? stagesResp ?? []) as PipelineStage[];
  return {
    pipeline: latestPipeline ?? null,
    stages: Array.isArray(stages) ? stages : [],
  };
}

export function useDeleteWorkItem() {
  return useMutation({
    mutationFn: (workItemId: string) =>
      customInstance<undefined>(`/api/v1/work-items/${workItemId}`, { method: 'DELETE' }),
  });
}

export function useUpdateWorkItem() {
  return useMutation({
    mutationFn: ({
      workItemId,
      data,
    }: {
      workItemId: string;
      data: Record<string, unknown>;
    }) =>
      customInstance<SingleResponse<WorkItem>>(
        `/api/v1/work-items/${workItemId}`,
        {
          method: 'PATCH',
          body: JSON.stringify(data),
        },
      ),
  });
}
