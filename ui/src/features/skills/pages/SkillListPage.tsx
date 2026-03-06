import { useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Textarea,
  Select,
  Loader,
  Center,
  ActionIcon,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconEdit } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useSkillsListSkills,
  useSkillsRegisterSkill,
  useSkillsUpdateSkill,
  useSkillsDeleteSkill,
} from '@/generated/api/skills/skills';
import { EmptyState } from '@/shared/components/EmptyState';

interface Skill {
  skill_id: string;
  name: string;
  description: string;
  content: string;
  version: string;
  execution_mode: string;
}

export function Component() {
  const { data: resp, isLoading } = useSkillsListSkills();
  const registerMutation = useSkillsRegisterSkill();
  const updateMutation = useSkillsUpdateSkill();
  const deleteMutation = useSkillsDeleteSkill();
  const queryClient = useQueryClient();
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [editSkill, setEditSkill] = useState<Skill | null>(null);

  const createForm = useForm({
    initialValues: {
      skill_id: '',
      name: '',
      description: '',
      content: '',
      version: '1.0.0',
      execution_mode: 'inline',
    },
    validate: {
      skill_id: (v) => (v.trim() ? null : 'Required'),
      name: (v) => (v.trim() ? null : 'Required'),
    },
  });

  const editForm = useForm({
    initialValues: {
      name: '',
      description: '',
      content: '',
      version: '',
      execution_mode: 'inline',
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const skills = (resp?.data ?? []) as Skill[];

  const handleCreate = createForm.onSubmit((values) => {
    registerMutation.mutate(
      { data: { ...values, input_schema: {}, output_schema: {} } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Created', message: `Skill "${values.name}" registered`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/skills'] });
          createForm.reset();
          closeCreate();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to register skill', color: 'red' });
        },
      },
    );
  });

  const openEdit = (skill: Skill) => {
    setEditSkill(skill);
    editForm.setValues({
      name: skill.name,
      description: skill.description ?? '',
      content: skill.content ?? '',
      version: skill.version,
      execution_mode: skill.execution_mode,
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editSkill) return;
    updateMutation.mutate(
      { skillId: editSkill.skill_id, data: values },
      {
        onSuccess: () => {
          notifications.show({ title: 'Updated', message: `Skill "${values.name}" updated`, color: 'green' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/skills'] });
          setEditSkill(null);
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update skill', color: 'red' });
        },
      },
    );
  });

  const handleDelete = (skillId: string) => {
    deleteMutation.mutate(
      { skillId },
      {
        onSuccess: () => {
          notifications.show({ title: 'Deleted', message: 'Skill removed', color: 'orange' });
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/skills'] });
        },
      },
    );
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Skills</Title>
        <Button onClick={openCreate}>Register Skill</Button>
      </Group>

      {skills.length === 0 ? (
        <EmptyState
          title="No skills registered"
          description="Register a skill to extend agent capabilities"
          actionLabel="Register Skill"
          onAction={openCreate}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Version</Table.Th>
              <Table.Th>Mode</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {skills.map((s) => (
              <Table.Tr key={s.skill_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(s)}>
                <Table.Td>{s.skill_id}</Table.Td>
                <Table.Td>{s.name}</Table.Td>
                <Table.Td><Text size="sm" lineClamp={1}>{s.description || '—'}</Text></Table.Td>
                <Table.Td>{s.version}</Table.Td>
                <Table.Td>{s.execution_mode}</Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    <ActionIcon variant="subtle" onClick={(e) => { e.stopPropagation(); openEdit(s); }}>
                      <IconEdit size={16} />
                    </ActionIcon>
                    <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(s.skill_id); }}>
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Register Skill" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Skill ID" placeholder="my-skill" {...createForm.getInputProps('skill_id')} />
            <TextInput label="Name" placeholder="My Skill" {...createForm.getInputProps('name')} />
            <Textarea label="Description" placeholder="What this skill does" autosize minRows={2} {...createForm.getInputProps('description')} />
            <Textarea
              label="Content"
              placeholder="Skill content / prompt template (OpenSkill format)"
              autosize minRows={6}
              styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
              {...createForm.getInputProps('content')}
            />
            <TextInput label="Version" {...createForm.getInputProps('version')} />
            <Select
              label="Execution Mode"
              data={[{ value: 'inline', label: 'Inline' }, { value: 'sandbox', label: 'Sandbox' }]}
              {...createForm.getInputProps('execution_mode')}
            />
            <Button type="submit" loading={registerMutation.isPending}>Register</Button>
          </Stack>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal opened={!!editSkill} onClose={() => setEditSkill(null)} title={`Edit Skill: ${editSkill?.skill_id ?? ''}`} size="lg">
        <form onSubmit={handleEdit}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <Textarea
              label="Content"
              autosize minRows={8}
              styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
              {...editForm.getInputProps('content')}
            />
            <TextInput label="Version" {...editForm.getInputProps('version')} />
            <Select
              label="Execution Mode"
              data={[{ value: 'inline', label: 'Inline' }, { value: 'sandbox', label: 'Sandbox' }]}
              {...editForm.getInputProps('execution_mode')}
            />
            <Button type="submit" loading={updateMutation.isPending}>Save Changes</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
