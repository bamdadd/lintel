import { useState, useEffect } from 'react';
import { Text, Tooltip, type TextProps } from '@mantine/core';

/** Format a date as a human-readable relative string. */
function formatTimeAgo(date: Date): string {
  const now = Date.now();
  const diffMs = now - date.getTime();

  if (diffMs < 0) return 'just now';

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  // Over 24 hours — show the date
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  });
}

/** How often to re-render based on the age of the date. */
function refreshInterval(date: Date): number {
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) return 5_000;       // < 1min: every 5s
  if (diffMs < 3_600_000) return 30_000;    // < 1hr: every 30s
  if (diffMs < 86_400_000) return 300_000;  // < 24hr: every 5min
  return 0;                                  // > 24hr: no refresh
}

interface TimeAgoProps extends Omit<TextProps, 'children'> {
  /** ISO date string or Date object. */
  date: string | Date | null | undefined;
  /** Fallback text when date is empty. */
  fallback?: string;
}

export function TimeAgo({ date, fallback = '—', ...textProps }: TimeAgoProps) {
  const parsed = date ? new Date(typeof date === 'string' ? date : date) : null;
  const isValid = parsed && !isNaN(parsed.getTime());

  const [, setTick] = useState(0);

  useEffect(() => {
    if (!isValid) return;
    const interval = refreshInterval(parsed);
    if (interval === 0) return;
    const id = setInterval(() => setTick((t) => t + 1), interval);
    return () => clearInterval(id);
  }, [isValid, parsed]);

  if (!isValid) {
    return <Text {...textProps}>{fallback}</Text>;
  }

  const relative = formatTimeAgo(parsed);
  const absolute = parsed.toLocaleString();

  return (
    <Tooltip label={absolute} openDelay={300}>
      <Text {...textProps}>{relative}</Text>
    </Tooltip>
  );
}
