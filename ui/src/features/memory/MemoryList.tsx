import { useState } from 'react';
import { Stack, Pagination, Center, Loader, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useMemoryList, useDeleteMemory } from './hooks/useMemory';
import { MemoryCard } from './components/MemoryCard';
import { MemoryDetail } from './MemoryDetail';
import type { MemoryFact } from './hooks/useMemory';

interface MemoryListProps {
  projectId: string;
  memoryType: string;
}

export function MemoryList({ projectId, memoryType }: MemoryListProps) {
  const [page, setPage] = useState(1);
  const [selectedMemory, setSelectedMemory] = useState<MemoryFact | null>(null);

  const { data: resp, isLoading } = useMemoryList({
    project_id: projectId,
    memory_type: memoryType,
    page,
    page_size: 20,
  });

  const deleteMut = useDeleteMemory();

  const items = resp?.data?.items ?? [];
  const total = resp?.data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  const handleDelete = (id: string) => {
    deleteMut.mutate(id, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Memory fact removed', color: 'green' });
        setSelectedMemory(null);
      },
      onError: () => {
        notifications.show({ title: 'Error', message: 'Failed to delete memory', color: 'red' });
      },
    });
  };

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  if (items.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No memories yet — memories are created automatically after workflow completions
      </Text>
    );
  }

  return (
    <>
      <Stack gap="sm">
        {items.map((memory) => (
          <MemoryCard
            key={memory.id}
            memory={memory}
            onDelete={handleDelete}
            onClick={setSelectedMemory}
          />
        ))}

        {totalPages > 1 && (
          <Center pt="md">
            <Pagination value={page} onChange={setPage} total={totalPages} />
          </Center>
        )}
      </Stack>

      <MemoryDetail
        memory={selectedMemory}
        opened={!!selectedMemory}
        onClose={() => setSelectedMemory(null)}
        onDelete={handleDelete}
      />
    </>
  );
}
