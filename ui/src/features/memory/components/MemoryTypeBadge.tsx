import { Badge } from '@mantine/core';

const typeColors: Record<string, string> = {
  long_term: 'blue',
  episodic: 'grape',
};

const typeLabels: Record<string, string> = {
  long_term: 'Long-term',
  episodic: 'Episodic',
};

export function MemoryTypeBadge({ type }: { type: string }) {
  return (
    <Badge color={typeColors[type] ?? 'gray'} variant="light" size="sm">
      {typeLabels[type] ?? type}
    </Badge>
  );
}
