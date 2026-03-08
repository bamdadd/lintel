import { useState, useEffect, useRef, useCallback } from 'react';

interface Message {
  message_id: string;
  role: string;
  content: string;
  display_name: string | null;
  timestamp: string;
}

/**
 * Subscribe to real-time chat message updates via SSE.
 * Falls back gracefully if the connection fails.
 */
export function useChatSSE(conversationId: string | null) {
  const [sseMessages, setSSEMessages] = useState<Message[]>([]);
  const sourceRef = useRef<EventSource | null>(null);

  const reset = useCallback(() => {
    setSSEMessages([]);
  }, []);

  useEffect(() => {
    if (!conversationId || conversationId.startsWith('new-')) {
      setSSEMessages([]);
      return;
    }

    const source = new EventSource(
      `/api/v1/chat/conversations/${conversationId}/events`,
    );
    sourceRef.current = source;

    source.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as Message;
        setSSEMessages((prev) => {
          // Deduplicate by message_id
          if (prev.some((m) => m.message_id === msg.message_id)) return prev;
          return [...prev, msg];
        });
      } catch {
        // skip malformed
      }
    };

    source.onerror = () => {
      // SSE will auto-reconnect; no action needed
    };

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [conversationId]);

  return { sseMessages, reset };
}
