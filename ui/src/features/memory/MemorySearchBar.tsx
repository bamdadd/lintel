import { useState } from 'react';
import { TextInput, Stack, Text, Card, Group, Badge, Loader, Center } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useMemorySearch } from './hooks/useMemory';
import { MemoryTypeBadge } from './components/MemoryTypeBadge';

interface MemorySearchBarProps {
  projectId: string;
}

export function MemorySearchBar({ projectId }: MemorySearchBarProps) {
  const [query, setQuery] = useState('');
  const [debouncedQuery] = useDebouncedValue(query, 300);

  const { data: resp, isLoading } = useMemorySearch({
    q: debouncedQuery,
    project_id: projectId,
  });

  const results = resp?.data?.results ?? [];

  return (
    <Stack gap="md">
      <TextInput
        placeholder="Search memories semantically..."
        leftSection={<IconSearch size={16} />}
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        size="md"
      />

      {isLoading && debouncedQuery.length >= 2 && (
        <Center py="md">
          <Loader size="sm" />
        </Center>
      )}

      {!isLoading && debouncedQuery.length >= 2 && results.length === 0 && (
        <Text c="dimmed" ta="center" py="md">
          No results found for &ldquo;{debouncedQuery}&rdquo;
        </Text>
      )}

      {results.length > 0 && (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {resp?.data?.total ?? results.length} result{results.length !== 1 ? 's' : ''} for &ldquo;{resp?.data?.query}&rdquo;
          </Text>
          {results.map((chunk) => (
            <Card key={chunk.id} shadow="xs" padding="sm" radius="md" withBorder>
              <Stack gap="xs">
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="xs">
                    <MemoryTypeBadge type={chunk.memory_type} />
                    <Badge variant="outline" size="sm" color="teal">
                      {chunk.fact_type}
                    </Badge>
                  </Group>
                  <Badge variant="light" size="xs" color="yellow">
                    Score: {chunk.score.toFixed(3)}
                  </Badge>
                </Group>
                <Text size="sm">{chunk.content}</Text>
                <Text size="xs" c="dimmed">
                  {new Date(chunk.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </Text>
              </Stack>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
