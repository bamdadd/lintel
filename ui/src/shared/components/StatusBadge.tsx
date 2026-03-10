import { Badge, type BadgeProps } from '@mantine/core';

const statusColors: Record<string, string> = {
  // Pipeline / stage statuses
  pending: 'yellow',
  running: 'blue',
  succeeded: 'green',
  completed: 'green',
  failed: 'red',
  error: 'red',
  errored: 'red',
  cancelled: 'orange',
  skipped: 'gray',
  waiting_approval: 'yellow',
  approved: 'teal',
  rejected: 'red',

  // Work item statuses
  open: 'blue',
  in_progress: 'yellow',
  in_review: 'orange',
  merged: 'teal',
  closed: 'gray',
  done: 'green',
  blocked: 'red',

  // Sandbox statuses
  creating: 'cyan',
  active: 'green',
  stopped: 'gray',
  destroyed: 'gray',
  archived: 'gray',
  paused: 'orange',

  // SSE / stream statuses
  connecting: 'gray',
  streaming: 'blue',
  ended: 'green',
  started: 'teal',

  // Approval statuses
  expired: 'gray',
  unknown: 'yellow',
};

export function getStatusColor(status: string): string {
  return statusColors[status] ?? 'gray';
}

interface StatusBadgeProps extends Omit<BadgeProps, 'color' | 'children'> {
  status: string;
}

export function StatusBadge({ status, ...rest }: StatusBadgeProps) {
  return (
    <Badge color={getStatusColor(status)} variant="dot" {...rest}>
      {status?.replace(/_/g, ' ')}
    </Badge>
  );
}
