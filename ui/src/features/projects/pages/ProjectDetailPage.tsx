import { useParams, useNavigate } from 'react-router';
import {
  Title,
  Stack,
  Paper,
  Text,
  Group,
  Button,
  Badge,
  Loader,
  Center,
} from '@mantine/core';
import { useProjectsGetProject } from '@/generated/api/projects/projects';

interface ProjectData {
  project_id: string;
  name: string;
  repo_id: string;
  channel_id: string;
  workspace_id: string;
  workflow_definition_id: string;
  default_branch: string;
  credential_ids: string[];
  ai_provider_id: string;
  status: string;
}

export function Component() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { data: resp, isLoading } = useProjectsGetProject(projectId ?? '', {
    query: { enabled: !!projectId },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const project = resp?.data as ProjectData | undefined;

  if (!project) {
    return <Text>Project not found</Text>;
  }

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/projects')}>&larr; Back</Button>
        <Title order={2}>{project.name}</Title>
        <Badge>{project.status}</Badge>
      </Group>

      <Paper withBorder p="lg" radius="md">
        <Stack gap="xs">
          <Text><strong>Project ID:</strong> {project.project_id}</Text>
          <Text><strong>Repository:</strong> {project.repo_id}</Text>
          <Text><strong>Default Branch:</strong> {project.default_branch}</Text>
          <Text><strong>Workflow:</strong> {project.workflow_definition_id}</Text>
          <Text><strong>Channel:</strong> {project.channel_id || '—'}</Text>
          <Text><strong>Workspace:</strong> {project.workspace_id || '—'}</Text>
          <Text><strong>AI Provider:</strong> {project.ai_provider_id || '—'}</Text>
          <Text><strong>Credentials:</strong> {project.credential_ids?.length ? project.credential_ids.join(', ') : '—'}</Text>
        </Stack>
      </Paper>
    </Stack>
  );
}
