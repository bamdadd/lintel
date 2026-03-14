import { useState, useEffect, useCallback, useRef } from 'react';

interface StageUpdate {
  type: 'stage_update';
  stage_id: string;
  name: string;
  status: string;
}

interface PipelineStatusUpdate {
  type: 'pipeline_status' | 'pipeline_complete';
  status: string;
}

type PipelineEvent = StageUpdate | PipelineStatusUpdate;

/**
 * Subscribe to real-time pipeline stage updates via SSE.
 * Returns a map of stage_id -> latest status, plus the pipeline status.
 * Call `invalidate()` from the consumer to trigger a React Query refetch.
 */
export function usePipelineSSE(runId: string | null) {
  const [stageStatuses, setStageStatuses] = useState<Record<string, string>>({});
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const callbackRef = useRef<(() => void) | null>(null);

  const onUpdate = useCallback((cb: () => void) => {
    callbackRef.current = cb;
  }, []);

  useEffect(() => {
    if (!runId) return;

    const source = new EventSource(`/api/v1/pipelines/${runId}/events`);

    source.onopen = () => setConnected(true);

    source.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as PipelineEvent;

        if (event.type === 'stage_update') {
          setStageStatuses((prev) => ({
            ...prev,
            [(event as StageUpdate).stage_id]: (event as StageUpdate).status,
          }));
          callbackRef.current?.();
        } else if (event.type === 'pipeline_status' || event.type === 'pipeline_complete') {
          setPipelineStatus(event.status);
          callbackRef.current?.();
        }

        if (event.type === 'pipeline_complete') {
          source.close();
          setConnected(false);
        }
      } catch {
        // skip malformed
      }
    };

    source.onerror = () => {
      // Don't close — let EventSource auto-reconnect on transient errors.
      // It will fire onopen again once reconnected.
      setConnected(false);
    };

    return () => {
      source.close();
      setConnected(false);
    };
  }, [runId]);

  return { stageStatuses, pipelineStatus, connected, onUpdate };
}
