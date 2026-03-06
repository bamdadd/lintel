import { Stack, Text, Title, Button } from '@mantine/core';

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <Stack align="center" py="xl" gap="md">
      <Title order={3}>{title}</Title>
      <Text c="dimmed">{description}</Text>
      {actionLabel && onAction && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </Stack>
  );
}
