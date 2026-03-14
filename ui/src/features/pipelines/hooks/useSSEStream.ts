import { useState, useEffect } from 'react';

export interface StreamEvent {
  event_type: string;
  step_id: string | null;
  timestamp_ms: number;
  payload?: Record<string, unknown>;
  [key: string]: unknown;
}

type StreamStatus = 'connecting' | 'streaming' | 'ended' | 'error';

export function useSSEStream(runId: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>('connecting');

  useEffect(() => {
    if (!runId) return;

    setEvents([]);
    setStatus('connecting');

    const source = new EventSource(`/api/v1/runs/${runId}/stream`);

    const handleEvent = (e: MessageEvent) => {
      const event = JSON.parse(e.data) as StreamEvent;
      setEvents((prev) => [...prev, event]);
      if (event.event_type === 'status' || event.event_type === 'PipelineRunStarted') {
        setStatus('streaming');
      }
      if (event.event_type === 'end' || event.event_type === 'PipelineRunCompleted' || event.event_type === 'PipelineRunFailed') {
        setStatus('ended');
        source.close();
      }
    };

    const eventTypes = [
      'PipelineRunStarted', 'PipelineStageCompleted', 'PipelineRunCompleted', 'PipelineRunFailed',
      'initialize-step', 'start-step', 'finish-step',
      'tool-call', 'tool-result', 'log', 'status', 'end',
    ];

    for (const type of eventTypes) {
      source.addEventListener(type, handleEvent);
    }

    source.onerror = () => {
      // Don't close — let EventSource auto-reconnect on transient errors.
      setStatus('error');
    };

    return () => source.close();
  }, [runId]);

  return { events, status };
}
