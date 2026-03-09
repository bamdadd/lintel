import { Badge } from '@mantine/core';

const statusColors: Record<string, string> = {
  active: 'green',
  running: 'blue',
  pending: 'yellow',
  completed: 'green',
  succeeded: 'green',
  failed: 'red',
  error: 'red',
  skipped: 'gray',
  archived: 'gray',
  destroyed: 'gray',
  closed: 'gray',
  paused: 'orange',
  creating: 'cyan',
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge color={statusColors[status] ?? 'gray'}>{status}</Badge>;
}
