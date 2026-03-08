import {
  Title,
  Stack,
  SimpleGrid,
  Paper,
  Text,
  Badge,
  Loader,
  Center,
  Button,
  Group,
  Switch,
} from '@mantine/core';
import { useNavigate } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useWorkflowDefinitionsListWorkflowDefinitions } from '@/generated/api/workflow-definitions/workflow-definitions';
import { customInstance } from '@/shared/api/client';
import { EmptyState } from '@/shared/components/EmptyState';

interface WorkflowDef {
  definition_id?: string;
  name?: string;
  description?: string;
  is_template?: boolean;
  stage_names?: string[];
  tags?: string[];
  is_builtin?: boolean;
  enabled?: boolean;
}

const TAG_COLORS: Record<string, string> = {
  feature: 'blue',
  bugfix: 'red',
  hotfix: 'red',
  review: 'orange',
  quality: 'orange',
  refactor: 'violet',
  security: 'pink',
  audit: 'pink',
  incident: 'red',
  documentation: 'teal',
  docs: 'teal',
  release: 'green',
  deployment: 'green',
  onboarding: 'cyan',
  spike: 'indigo',
  research: 'indigo',
};

function tagColor(tag: string): string {
  return TAG_COLORS[tag] ?? 'gray';
}

export function Component() {
  const { data: resp, isLoading } = useWorkflowDefinitionsListWorkflowDefinitions();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const definitions = (resp?.data ?? []) as WorkflowDef[];

  const toggleMut = useMutation({
    mutationFn: (definitionId: string) =>
      customInstance(`/api/v1/workflow-definitions/${definitionId}/toggle`, {
        method: 'PATCH',
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['/api/v1/workflow-definitions'] }),
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Workflows</Title>
        <Button onClick={() => void navigate('/workflows/editor')}>
          New Workflow
        </Button>
      </Group>

      {definitions.length === 0 ? (
        <EmptyState
          title="No workflow definitions"
          description="Create your first workflow definition."
          actionLabel="Create Workflow"
          onAction={() => void navigate('/workflows/editor')}
        />
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {definitions.map((d) => {
            const id = d.definition_id ?? '';
            const stages = d.stage_names ?? [];
            const tags = d.tags ?? [];
            const enabled = d.enabled !== false;
            return (
              <Paper
                key={id}
                withBorder
                p="md"
                radius="md"
                style={{ cursor: 'pointer', opacity: enabled ? 1 : 0.5 }}
                onClick={() => void navigate(`/workflows/editor/${id}`)}
              >
                <Group gap="xs" mb="sm" justify="space-between">
                  <Group gap="xs">
                    <Text fw={600} size="md">{d.name ?? id}</Text>
                    {d.is_builtin && (
                      <Badge variant="light" color="gray" size="xs">
                        built-in
                      </Badge>
                    )}
                  </Group>
                  <Switch
                    size="sm"
                    checked={enabled}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleMut.mutate(id);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    aria-label={`Toggle ${d.name}`}
                  />
                </Group>
                {d.description && (
                  <Text size="sm" c="dimmed" lineClamp={2} mb="sm">
                    {d.description}
                  </Text>
                )}
                <Text size="xs" c="dimmed" mb="xs">
                  {stages.length} stage{stages.length !== 1 ? 's' : ''}
                </Text>
                {tags.length > 0 && (
                  <Group gap={4}>
                    {tags.map((tag) => (
                      <Badge key={tag} size="xs" variant="light" color={tagColor(tag)}>
                        {tag}
                      </Badge>
                    ))}
                  </Group>
                )}
              </Paper>
            );
          })}
        </SimpleGrid>
      )}
    </Stack>
  );
}
