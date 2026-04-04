import { useQuery } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

interface BoardSummary {
  board_id: string;
  name: string;
  project_id: string;
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
  const { data: boardsResp } = useQuery({
    queryKey: ['/api/v1/boards', 'all', 'nav-cache'],
    queryFn: () =>
      customInstance<ListResponse<BoardSummary>>('/api/v1/boards'),
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
