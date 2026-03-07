import {
  Title,
  Stack,
  SimpleGrid,
  Paper,
  Text,
  Badge,
  Loader,
  Center,
  Group,
} from '@mantine/core';
import { useNavigate } from 'react-router';
import { useAgentsListAgentDefinitions } from '@/generated/api/agents/agents';

interface AgentDef {
  agent_id: string;
  name: string;
  role: string;
  category?: string;
  description?: string;
  model_policy?: { provider?: string; model_name?: string };
  model_provider?: string;
  model_name?: string;
  is_builtin?: boolean;
  tags?: string[];
}

const CATEGORY_ORDER = [
  'engineering',
  'quality',
  'operations',
  'leadership',
  'communication',
  'design',
] as const;

const CATEGORY_LABELS: Record<string, string> = {
  engineering: 'Engineering',
  quality: 'Quality & Security',
  operations: 'Operations',
  leadership: 'Leadership',
  communication: 'Communication',
  design: 'Design',
};

const CATEGORY_COLORS: Record<string, string> = {
  engineering: 'blue',
  quality: 'orange',
  operations: 'teal',
  leadership: 'violet',
  communication: 'cyan',
  design: 'pink',
};

export function Component() {
  const { data: defsResp, isLoading } = useAgentsListAgentDefinitions();
  const navigate = useNavigate();

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const definitions = (defsResp?.data ?? []) as AgentDef[];

  // Group by category
  const grouped = new Map<string, AgentDef[]>();
  for (const def of definitions) {
    const cat = def.category ?? 'engineering';
    if (!grouped.has(cat)) grouped.set(cat, []);
    grouped.get(cat)!.push(def);
  }

  // Sort categories in defined order
  const sortedCategories = [...grouped.keys()].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a as typeof CATEGORY_ORDER[number]);
    const bi = CATEGORY_ORDER.indexOf(b as typeof CATEGORY_ORDER[number]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <Stack gap="lg">
      <Title order={2}>Agents</Title>
      {sortedCategories.map((category) => {
        const agents = grouped.get(category) ?? [];
        const color = CATEGORY_COLORS[category] ?? 'gray';
        return (
          <Stack key={category} gap="sm">
            <Group gap="xs">
              <Badge
                size="lg"
                variant="light"
                color={color}
              >
                {CATEGORY_LABELS[category] ?? category}
              </Badge>
              <Text size="sm" c="dimmed">
                {agents.length} agent{agents.length !== 1 ? 's' : ''}
              </Text>
            </Group>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              {agents.map((def) => {
                const provider =
                  def.model_policy?.provider ??
                  def.model_provider ??
                  'default';
                const model =
                  def.model_policy?.model_name ??
                  def.model_name ??
                  'default';
                return (
                  <Paper
                    key={def.agent_id}
                    withBorder
                    p="md"
                    radius="md"
                    style={{ cursor: 'pointer' }}
                    onClick={() =>
                      void navigate(`/agents/${def.agent_id}`)
                    }
                  >
                    <Group gap="xs" mb="sm">
                      <Badge color={color}>{def.role}</Badge>
                      {def.is_builtin && (
                        <Badge
                          variant="light"
                          color="gray"
                          size="xs"
                        >
                          built-in
                        </Badge>
                      )}
                    </Group>
                    <Text fw={600} mb={4}>
                      {def.name}
                    </Text>
                    {def.description && (
                      <Text
                        size="sm"
                        c="dimmed"
                        lineClamp={2}
                        mb="xs"
                      >
                        {def.description}
                      </Text>
                    )}
                    <Text size="xs" c="dimmed">
                      {provider} / {model}
                    </Text>
                  </Paper>
                );
              })}
            </SimpleGrid>
          </Stack>
        );
      })}
    </Stack>
  );
}
