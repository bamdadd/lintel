import { useState, useCallback } from 'react';
import {
  Stack, Paper, Text, Group, Button, Textarea, Badge, Anchor, Center,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { IconGitBranch, IconExternalLink, IconDeviceFloppy } from '@tabler/icons-react';
import { useProjectsUpdateProject } from '@/generated/api/projects/projects';
import type { UpdateProjectRequest } from '@/generated/models';

interface RepoInfo {
  repo_id: string;
  name: string;
  url: string;
}

interface ProjectRepositoriesTabProps {
  projectId: string;
  repoIds: string[];
  repoDescriptions: Record<string, string>;
  allRepos: RepoInfo[];
}

export function ProjectRepositoriesTab({
  projectId,
  repoIds,
  repoDescriptions,
  allRepos,
}: ProjectRepositoriesTabProps) {
  const qc = useQueryClient();
  const updateMut = useProjectsUpdateProject();
  const [descriptions, setDescriptions] = useState<Record<string, string>>(() => ({
    ...repoDescriptions,
  }));
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const linkedRepos = repoIds
    .map((id) => allRepos.find((r) => r.repo_id === id))
    .filter((r): r is RepoInfo => r != null);

  const handleChange = useCallback((repoId: string, value: string) => {
    setDescriptions((prev) => ({ ...prev, [repoId]: value }));
    setDirty((prev) => {
      const next = new Set(prev);
      if (value !== (repoDescriptions[repoId] ?? '')) {
        next.add(repoId);
      } else {
        next.delete(repoId);
      }
      return next;
    });
  }, [repoDescriptions]);

  const handleSave = useCallback(() => {
    updateMut.mutate(
      {
        projectId,
        data: { repo_descriptions: descriptions } as UpdateProjectRequest & { repo_descriptions: Record<string, string> },
      },
      {
        onSuccess: () => {
          notifications.show({ title: 'Saved', message: 'Repository descriptions updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/projects'] });
          setDirty(new Set());
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to save descriptions', color: 'red' });
        },
      },
    );
  }, [projectId, descriptions, updateMut, qc]);

  const saveButton = dirty.size > 0 ? (
    <Group justify="flex-end">
      <Button
        leftSection={<IconDeviceFloppy size={16} />}
        onClick={handleSave}
        loading={updateMut.isPending}
      >
        Save Descriptions
      </Button>
    </Group>
  ) : null;

  if (linkedRepos.length === 0) {
    return (
      <Center py="xl">
        <Text c="dimmed">No repositories linked to this project. Add repositories in the Edit dialog.</Text>
      </Center>
    );
  }

  return (
    <Stack gap="md">
      {saveButton}

      {linkedRepos.map((repo) => (
        <Paper key={repo.repo_id} withBorder p="md" radius="md">
          <Stack gap="xs">
            <Group justify="space-between">
              <Group gap="xs">
                <IconGitBranch size={16} />
                <Text fw={600}>{repo.name}</Text>
                {dirty.has(repo.repo_id) && (
                  <Badge size="xs" color="yellow" variant="light">unsaved</Badge>
                )}
              </Group>
              <Anchor href={repo.url} target="_blank" size="sm">
                {repo.url} <IconExternalLink size={12} style={{ verticalAlign: 'middle' }} />
              </Anchor>
            </Group>
            <Textarea
              placeholder="Describe what this repository does in the context of this project..."
              autosize
              minRows={2}
              maxRows={6}
              value={descriptions[repo.repo_id] ?? ''}
              onChange={(e) => handleChange(repo.repo_id, e.currentTarget.value)}
            />
          </Stack>
        </Paper>
      ))}

      {saveButton}
    </Stack>
  );
}
