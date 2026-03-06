import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Select,
  Loader,
  Center,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useSkillsListSkills, useSkillsRegisterSkill } from '@/generated/api/skills/skills';
import { EmptyState } from '@/shared/components/EmptyState';

interface Skill {
  skill_id: string;
  name: string;
  version: string;
  execution_mode: string;
}

export function Component() {
  const { data: resp, isLoading } = useSkillsListSkills();
  const mutation = useSkillsRegisterSkill();
  const queryClient = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      skill_id: '',
      name: '',
      version: '1.0.0',
      execution_mode: 'inline',
    },
    validate: {
      skill_id: (v) => (v.trim() ? null : 'Required'),
      name: (v) => (v.trim() ? null : 'Required'),
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const skills = (resp?.data ?? []) as Skill[];

  const handleSubmit = form.onSubmit((values) => {
    mutation.mutate(
      { data: { ...values, input_schema: {}, output_schema: {} } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: `Skill "${values.name}" registered`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/skills'] });
          form.reset();
          close();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to register skill', color: 'red' });
        },
      },
    );
  });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Skills</Title>
        <Button onClick={open}>Register Skill</Button>
      </Group>

      {skills.length === 0 ? (
        <EmptyState
          title="No skills registered"
          description="Register a skill to extend agent capabilities"
          actionLabel="Register Skill"
          onAction={open}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Version</Table.Th>
              <Table.Th>Mode</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {skills.map((s) => (
              <Table.Tr key={s.skill_id}>
                <Table.Td>{s.skill_id}</Table.Td>
                <Table.Td>{s.name}</Table.Td>
                <Table.Td>{s.version}</Table.Td>
                <Table.Td>{s.execution_mode}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Register Skill">
        <form onSubmit={handleSubmit}>
          <Stack gap="sm">
            <TextInput label="Skill ID" placeholder="my-skill" {...form.getInputProps('skill_id')} />
            <TextInput label="Name" placeholder="My Skill" {...form.getInputProps('name')} />
            <TextInput label="Version" {...form.getInputProps('version')} />
            <Select
              label="Execution Mode"
              data={[
                { value: 'inline', label: 'Inline' },
                { value: 'sandbox', label: 'Sandbox' },
              ]}
              {...form.getInputProps('execution_mode')}
            />
            <Button type="submit" loading={mutation.isPending}>Register</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
