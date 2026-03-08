import { useQuery, useMutation } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

interface BoardColumn {
  column_id: string;
  name: string;
  position: number;
  work_item_status: string;
}

export interface Board {
  board_id: string;
  project_id: string;
  name: string;
  columns: BoardColumn[];
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
