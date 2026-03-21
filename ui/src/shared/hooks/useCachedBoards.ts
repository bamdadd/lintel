import { useQuery } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

interface BoardSummary {
  board_id: string;
  name: string;
  project_id: string;
}

interface ProjectItem {
  project_id: string;
  name: string;
}

interface ListResponse<T> {
  data: T[];
}

/**
 * Fetches all boards across all projects with aggressive caching.
 * staleTime of 5 minutes means the sidebar won't re-fetch on every navigation.
 * A hard refresh (window reload) will always fetch fresh data.
 */
export function useCachedBoards() {
  const { data: projectsResp } = useQuery({
    queryKey: ['/api/v1/projects', 'nav-cache'],
    queryFn: () => customInstance<ListResponse<ProjectItem>>('/api/v1/projects'),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const firstProjectId = projects[0]?.project_id;

  const { data: boardsResp } = useQuery({
    queryKey: ['/api/v1/boards', firstProjectId, 'nav-cache'],
    queryFn: () =>
      customInstance<ListResponse<BoardSummary>>(
        `/api/v1/projects/${firstProjectId}/boards`,
      ),
    enabled: !!firstProjectId,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  const boards = (boardsResp?.data ?? []) as unknown as BoardSummary[];

  return boards.map((b) => ({
    label: b.name,
    path: `/boards/${b.board_id}`,
    boardId: b.board_id,
  }));
}
