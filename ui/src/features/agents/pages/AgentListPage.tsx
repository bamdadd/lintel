import {
  Title,
  Stack,
  SimpleGrid,
  Paper,
  Text,
  Badge,
  Loader,
  Center,
} from '@mantine/core';
import { useAgentsListAgentRoles, useAgentsListModelPolicies } from '@/generated/api/agents/agents';

export function Component() {
  const { data: rolesResp, isLoading: rolesLoading } = useAgentsListAgentRoles();
  const { data: policiesResp, isLoading: policiesLoading } = useAgentsListModelPolicies();

  if (rolesLoading || policiesLoading) return <Center py="xl"><Loader /></Center>;

  const roles = rolesResp?.data ?? [];
  const policies = policiesResp?.data as Record<string, { provider?: string; model_name?: string }> | undefined;

  return (
    <Stack gap="md">
      <Title order={2}>Agents</Title>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {roles.map((role: string) => {
          const policy = policies?.[role];
          return (
            <Paper key={role} withBorder p="md" radius="md">
              <Badge mb="sm">{role}</Badge>
              <Text size="sm">
                Provider: {policy?.provider ?? 'default'}
              </Text>
              <Text size="sm">
                Model: {policy?.model_name ?? 'default'}
              </Text>
            </Paper>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
