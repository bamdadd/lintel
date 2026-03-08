import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Switch,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useVariablesListVariables,
  useVariablesCreateVariable,
  useVariablesUpdateVariable,
  useVariablesDeleteVariable,
} from '@/generated/api/variables/variables';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { useEnvironmentsListEnvironments } from '@/generated/api/environments/environments';
import { EmptyState } from '@/shared/components/EmptyState';

interface VarItem {
  variable_id: string;
  key: string;
  value: string;
  project_id: string;
  environment_id: string;
  is_secret: boolean;
}

interface ProjectItem { project_id: string; name: string; }
interface EnvItem { environment_id: string; name: string; }

export function Component() {
  const { data: resp, isLoading } = useVariablesListVariables();
  const { data: projectsResp } = useProjectsListProjects();
  const { data: envsResp } = useEnvironmentsListEnvironments();
  const createMut = useVariablesCreateVariable();
  const updateMut = useVariablesUpdateVariable();
  const deleteMut = useVariablesDeleteVariable();
  const qc = useQueryClient();
  const [opened, { open, close }] = useDisclosure(false);
  const [editItem, setEditItem] = useState<VarItem | null>(null);

  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const envs = (envsResp?.data ?? []) as unknown as EnvItem[];
  const projectOptions = [{ value: '', label: '— Global —' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];
  const envOptions = [{ value: '', label: '— All —' }, ...envs.map((e) => ({ value: e.environment_id, label: e.name }))];

  const form = useForm({
    initialValues: { key: '', value: '', project_id: '', environment_id: '', is_secret: false },
    validate: { key: (v) => (v.trim() ? null : 'Required'), value: (v) => (v.trim() ? null : 'Required') },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const variables = (resp?.data ?? []) as VarItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(
      { data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: 'Variable added', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/variables'] });
          form.reset(); close();
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to create variable', color: 'red' }),
      },
    );
  });

  const openEdit = (v: VarItem) => {
    setEditItem(v);
  };

  const handleEditSave = (newValue: string) => {
    if (!editItem) return;
    updateMut.mutate(
      { variableId: editItem.variable_id, data: { value: newValue } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: 'Variable updated', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/variables'] });
          setEditItem(null);
        },
      },
    );
  };

  const handleDelete = (id: string) => {
    deleteMut.mutate({ variableId: id }, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Variable removed', color: 'orange' });
        void qc.invalidateQueries({ queryKey: ['/api/v1/variables'] });
        if (editItem?.variable_id === id) setEditItem(null);
      },
    });
  };

  const projectName = (id: string) => projects.find((p) => p.project_id === id)?.name ?? (id || 'Global');
  const envName = (id: string) => envs.find((e) => e.environment_id === id)?.name ?? (id || 'All');

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Variables</Title>
        <Button onClick={open}>Create Variable</Button>
      </Group>

      {variables.length === 0 ? (
        <EmptyState title="No variables" description="Create variables for configuration and secrets" actionLabel="Create Variable" onAction={open} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Key</Table.Th>
              <Table.Th>Value</Table.Th>
              <Table.Th>Project</Table.Th>
              <Table.Th>Environment</Table.Th>
              <Table.Th>Secret</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {variables.map((v) => (
              <Table.Tr key={v.variable_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(v)}>
                <Table.Td><code>{v.key}</code></Table.Td>
                <Table.Td>{v.is_secret ? '••••••••' : v.value}</Table.Td>
                <Table.Td>{projectName(v.project_id)}</Table.Td>
                <Table.Td>{envName(v.environment_id)}</Table.Td>
                <Table.Td>{v.is_secret && <Badge color="yellow" variant="light">Secret</Badge>}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(v.variable_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Create Variable">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Key" placeholder="DATABASE_URL" {...form.getInputProps('key')} />
            <TextInput label="Value" placeholder="postgres://..." {...form.getInputProps('value')} />
            <Select label="Project" data={projectOptions} {...form.getInputProps('project_id')} />
            <Select label="Environment" data={envOptions} {...form.getInputProps('environment_id')} />
            <Switch label="Secret" {...form.getInputProps('is_secret', { type: 'checkbox' })} />
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.key ?? ''}`}>
        <EditValueForm item={editItem} onSave={handleEditSave} loading={updateMut.isPending} />
      </Modal>
    </Stack>
  );
}

function EditValueForm({ item, onSave, loading }: { item: VarItem | null; onSave: (v: string) => void; loading: boolean }) {
  const [value, setValue] = useState(item?.value ?? '');
  if (!item) return null;
  return (
    <Stack gap="sm">
      <TextInput label="Value" value={value} onChange={(e) => setValue(e.currentTarget.value)} />
      <Button onClick={() => onSave(value)} loading={loading}>Save</Button>
    </Stack>
  );
}
