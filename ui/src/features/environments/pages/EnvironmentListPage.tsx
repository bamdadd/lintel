import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useEnvironmentsListEnvironments,
  useEnvironmentsCreateEnvironment,
  useEnvironmentsUpdateEnvironment,
  useEnvironmentsDeleteEnvironment,
} from '@/generated/api/environments/environments';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import type { EnvironmentType } from '@/generated/models/environmentType';
import { EmptyState } from '@/shared/components/EmptyState';

interface EnvItem {
  environment_id: string;
  name: string;
  env_type: string;
  project_id: string;
  config: Record<string, unknown> | null;
}

interface ProjectItem { project_id: string; name: string; }

const ENV_TYPES = [
  { value: 'development', label: 'Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
  { value: 'sandbox', label: 'Sandbox' },
];

const typeColor: Record<string, string> = { development: 'blue', staging: 'yellow', production: 'red', sandbox: 'grape' };

export function Component() {
  const { data: resp, isLoading } = useEnvironmentsListEnvironments();
  const { data: projectsResp } = useProjectsListProjects();
  const createMut = useEnvironmentsCreateEnvironment();
  const updateMut = useEnvironmentsUpdateEnvironment();
  const deleteMut = useEnvironmentsDeleteEnvironment();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<EnvItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const projectOptions = [{ value: '', label: '— None —' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];

  const form = useForm({
    initialValues: { name: '', env_type: 'development', project_id: '', config: '' },
    validate: { name: (v) => (v.trim() ? null : 'Required') },
  });

  const editFormState = useForm({
    initialValues: { name: '', env_type: 'development', config: '' },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const envs = (resp?.data ?? []) as unknown as EnvItem[];

  const handleCreate = form.onSubmit((values) => {
    let config: Record<string, unknown> | null = null;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON', color: 'red' }); return; }
    }
    createMut.mutate(
      { data: { ...values, env_type: values.env_type as EnvironmentType, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Environment created', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/environments'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
      },
    );
  });

  const openEdit = (env: EnvItem) => {
    setEditItem(env);
    editFormState.setValues({ name: env.name, env_type: env.env_type, config: env.config ? JSON.stringify(env.config, null, 2) : '' });
  };

  const handleEdit = editFormState.onSubmit((values) => {
    if (!editItem) return;
    let config: Record<string, unknown> | undefined;
    if (values.config.trim()) {
      try { config = JSON.parse(values.config); } catch { notifications.show({ title: 'Error', message: 'Invalid JSON', color: 'red' }); return; }
    }
    updateMut.mutate(
      { environmentId: editItem.environment_id, data: { name: values.name, env_type: values.env_type as EnvironmentType, config } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Environment updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/environments'] });
          setEditItem(null);
        },
      },
    );
  });

  const handleDelete = (id: string) => {
    deleteMut.mutate({ environmentId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Environment removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/environments'] });
        if (editItem?.environment_id === id) setEditItem(null);
      },
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Environments</Title>
        <Button onClick={open}>Create Environment</Button>
      </Group>

      {envs.length === 0 ? (
        <EmptyState title="No environments" description="Create environments for deployments" actionLabel="Create Environment" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Project</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {envs.map((e) => (
              <Table.Tr key={e.environment_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(e)}>
                <Table.Td>{e.name}</Table.Td>
                <Table.Td><Badge color={typeColor[e.env_type] ?? 'gray'}>{e.env_type}</Badge></Table.Td>
                <Table.Td>{projects.find((p) => p.project_id === e.project_id)?.name ?? (e.project_id || '—')}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(ev) => { ev.stopPropagation(); handleDelete(e.environment_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Environment">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="production-us-east" {...form.getInputProps('name')} />
            <Select label="Type" data={ENV_TYPES} {...form.getInputProps('env_type')} />
            <Select label="Project" data={projectOptions} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Config (JSON)" minRows={3} styles={{ input: { fontFamily: 'monospace' } }} {...form.getInputProps('config')} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`}>
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editFormState.getInputProps('name')} />
            <Select label="Type" data={ENV_TYPES} {...editFormState.getInputProps('env_type')} />
            <Textarea label="Config (JSON)" minRows={3} styles={{ input: { fontFamily: 'monospace' } }} {...editFormState.getInputProps('config')} />
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
