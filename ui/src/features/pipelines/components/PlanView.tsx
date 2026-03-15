import {
  Stack, Group, Text, Badge, Paper, ThemeIcon, Timeline,
} from '@mantine/core';
import {
  IconFileCode, IconSubtask,
} from '@tabler/icons-react';

interface PlanTask {
  title: string;
  description?: string;
  file_paths?: string[];
  complexity?: string;
}

interface Plan {
  tasks: PlanTask[];
  summary?: string;
  intent?: string;
}

const complexityColor: Record<string, string> = {
  S: 'green',
  M: 'blue',
  L: 'orange',
  XL: 'red',
};

interface PlanViewProps {
  plan: Plan | string;
}

export function PlanView({ plan: rawPlan }: PlanViewProps) {
  const plan: Plan = typeof rawPlan === 'string' ? parsePlan(rawPlan) : rawPlan;
  const tasks = plan.tasks ?? [];

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" fw={600}>Implementation Plan</Text>
        {plan.intent && (
          <Badge variant="light" size="sm">{plan.intent}</Badge>
        )}
      </Group>

      {plan.summary && (
        <Text size="sm" c="dimmed">{plan.summary}</Text>
      )}

      {tasks.length === 0 ? (
        <Text size="sm" c="dimmed">No tasks in plan</Text>
      ) : (
        <Timeline active={-1} bulletSize={24} lineWidth={2}>
          {tasks.map((task, i) => (
            <Timeline.Item
              key={i}
              bullet={
                <ThemeIcon size={24} variant="light" radius="xl" color="blue">
                  <IconSubtask size={14} />
                </ThemeIcon>
              }
              title={
                <Group gap="xs">
                  <Text size="sm" fw={500}>{task.title}</Text>
                  {task.complexity && (
                    <Badge
                      size="xs"
                      variant="filled"
                      color={complexityColor[task.complexity] ?? 'gray'}
                    >
                      {task.complexity}
                    </Badge>
                  )}
                </Group>
              }
            >
              <Stack gap={4} mt={4}>
                {task.description && (
                  <Text size="xs" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
                    {task.description}
                  </Text>
                )}
                {task.file_paths && task.file_paths.length > 0 && (
                  <Group gap={4} wrap="wrap">
                    {task.file_paths.map((fp) => (
                      <Badge
                        key={fp}
                        variant="outline"
                        size="xs"
                        color="gray"
                        radius="sm"
                        leftSection={<IconFileCode size={10} />}
                      >
                        {fp}
                      </Badge>
                    ))}
                  </Group>
                )}
              </Stack>
            </Timeline.Item>
          ))}
        </Timeline>
      )}

      <Paper p="xs" bg="var(--mantine-color-body)" radius="sm" withBorder>
        <Text size="xs" c="dimmed">
          {tasks.length} task{tasks.length !== 1 ? 's' : ''}
          {tasks.some((t) => t.complexity) && (
            <> &middot; Complexity: {tasks.filter((t) => t.complexity).map((t) => t.complexity).join(', ')}</>
          )}
        </Text>
      </Paper>
    </Stack>
  );
}

function parsePlan(content: string): Plan {
  try {
    return JSON.parse(content);
  } catch {
    return {
      tasks: [{ title: 'Plan', description: content }],
    };
  }
}
