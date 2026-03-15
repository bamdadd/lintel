import { useState } from 'react';
import { Modal, Stack, Text, Group, Badge, Button, Code, Divider } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { MemoryTypeBadge } from './components/MemoryTypeBadge';
import type { MemoryFact } from './hooks/useMemory';

interface MemoryDetailProps {
  memory: MemoryFact | null;
  opened: boolean;
  onClose: () => void;
  onDelete: (id: string) => void;
}

export function MemoryDetail({ memory, opened, onClose, onDelete }: MemoryDetailProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (!memory) return null;

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    onDelete(memory.id);
    setConfirmDelete(false);
  };

  const handleClose = () => {
    setConfirmDelete(false);
    onClose();
  };

  return (
    <Modal opened={opened} onClose={handleClose} title="Memory Detail" size="lg">
      <Stack gap="md">
        <Group gap="xs">
          <MemoryTypeBadge type={memory.memory_type} />
          <Badge variant="outline" size="sm" color="teal">
            {memory.fact_type}
          </Badge>
        </Group>

        <Divider />

        <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
          {memory.content}
        </Text>

        <Divider />

        <Stack gap="xs">
          <Group gap="xs">
            <Text size="xs" fw={600} c="dimmed">Project ID:</Text>
            <Code>{memory.project_id}</Code>
          </Group>
          <Group gap="xs">
            <Text size="xs" fw={600} c="dimmed">Memory ID:</Text>
            <Code>{memory.id}</Code>
          </Group>
          {memory.embedding_id && (
            <Group gap="xs">
              <Text size="xs" fw={600} c="dimmed">Embedding ID:</Text>
              <Code>{memory.embedding_id}</Code>
            </Group>
          )}
          {memory.source_workflow_id && (
            <Group gap="xs">
              <Text size="xs" fw={600} c="dimmed">Source Workflow:</Text>
              <Code>{memory.source_workflow_id}</Code>
            </Group>
          )}
          <Group gap="xs">
            <Text size="xs" fw={600} c="dimmed">Created:</Text>
            <Text size="xs">{new Date(memory.created_at).toLocaleString()}</Text>
          </Group>
          <Group gap="xs">
            <Text size="xs" fw={600} c="dimmed">Updated:</Text>
            <Text size="xs">{new Date(memory.updated_at).toLocaleString()}</Text>
          </Group>
        </Stack>

        <Divider />

        <Group justify="flex-end">
          <Button variant="default" onClick={handleClose}>
            Close
          </Button>
          <Button
            color="red"
            variant={confirmDelete ? 'filled' : 'light'}
            leftSection={<IconTrash size={14} />}
            onClick={handleDelete}
          >
            {confirmDelete ? 'Confirm Delete' : 'Delete'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
