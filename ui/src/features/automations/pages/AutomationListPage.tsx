import { Button, Group, SimpleGrid, Stack, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconPlus } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';

import { EmptyState } from '@/shared/components/EmptyState';

import {
  useAutomationsCreateAutomation,
  useAutomationsListAutomations,
} from '@/generated/api/automations/automations';

import { AutomationCard } from '../components/AutomationCard';
import { AutomationFormModal } from '../components/AutomationFormModal';

export function Component() {
  const { data: resp, isLoading } = useAutomationsListAutomations();
  const createMut = useAutomationsCreateAutomation();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const automations = resp?.data ?? [];

  const handleCreate = (values: Parameters<typeof createMut.mutate>[0]['data']) => {
    createMut.mutate(
      { data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Automation created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/automations'] });
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to create automation', color: 'red' });
        },
      },
    );
  };

  if (isLoading) {
    return (
      <Stack gap="md">
        <Title order={2}>Automations</Title>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Automations</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={open}>
          Create Automation
        </Button>
      </Group>

      {automations.length === 0 ? (
        <EmptyState
          title="No automations"
          description="Create automations to run workflows on a schedule, in response to events, or on demand."
          actionLabel="Create Automation"
          onAction={open}
        />
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          {automations.map((auto: Record<string, unknown>) => (
            <AutomationCard
              key={String(auto.automation_id)}
              automation={{
                automation_id: String(auto.automation_id ?? ''),
                name: String(auto.name ?? ''),
                project_id: String(auto.project_id ?? ''),
                trigger_type: String(auto.trigger_type ?? ''),
                trigger_config: (auto.trigger_config ?? {}) as Record<string, unknown>,
                concurrency_policy: String(auto.concurrency_policy ?? ''),
                enabled: Boolean(auto.enabled),
              }}
            />
          ))}
        </SimpleGrid>
      )}

      <AutomationFormModal
        opened={opened}
        onClose={close}
        onSubmit={handleCreate}
        loading={createMut.isPending}
      />
    </Stack>
  );
}
