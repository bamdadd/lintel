import { useParams, useNavigate } from 'react-router';
import {
  Title,
  Stack,
  Paper,
  Text,
  Badge,
  Group,
  Button,
  Loader,
  Center,
  TextInput,
  NumberInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { useAgentsGetModelPolicy, useAgentsUpdateModelPolicy } from '@/generated/api/agents/agents';
import { useQueryClient } from '@tanstack/react-query';

export function Component() {
  const { role } = useParams<{ role: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: policyResp, isLoading } = useAgentsGetModelPolicy(role ?? '', {
    query: { enabled: !!role },
  });

  const mutation = useAgentsUpdateModelPolicy();

  const policy = policyResp?.data as
    | { role?: string; provider?: string; model_name?: string; max_tokens?: number; temperature?: number }
    | undefined;

  const form = useForm({
    initialValues: {
      provider: policy?.provider ?? 'anthropic',
      model_name: policy?.model_name ?? '',
      max_tokens: policy?.max_tokens ?? 4096,
      temperature: policy?.temperature ?? 0,
    },
  });

  // Update form when data loads
  if (policy && !form.isDirty()) {
    form.setValues({
      provider: policy.provider ?? 'anthropic',
      model_name: policy.model_name ?? '',
      max_tokens: policy.max_tokens ?? 4096,
      temperature: policy.temperature ?? 0,
    });
  }

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const handleSubmit = form.onSubmit((values) => {
    mutation.mutate(
      { role: role ?? '', data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Saved', message: `Policy for ${role} updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/agents/policies'] });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update policy', color: 'red' });
        },
      },
    );
  });

  return (
    <Stack gap="md">
      <Group>
        <Button variant="subtle" onClick={() => void navigate('/agents')}>
          &larr; Back
        </Button>
        <Title order={2}>Agent: {role}</Title>
        <Badge size="lg">{role}</Badge>
      </Group>

      <Paper withBorder p="lg" radius="md">
        <Title order={4} mb="md">Model Policy</Title>
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <TextInput label="Provider" {...form.getInputProps('provider')} />
            <TextInput label="Model Name" {...form.getInputProps('model_name')} />
            <NumberInput label="Max Tokens" min={1} {...form.getInputProps('max_tokens')} />
            <NumberInput
              label="Temperature"
              min={0}
              max={2}
              step={0.1}
              decimalScale={2}
              {...form.getInputProps('temperature')}
            />
            <Group>
              <Button type="submit" loading={mutation.isPending}>Save Policy</Button>
            </Group>
          </Stack>
        </form>
      </Paper>
    </Stack>
  );
}
