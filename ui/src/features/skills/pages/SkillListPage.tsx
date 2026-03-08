import { useState } from 'react';
import {
  Title,
  Stack,
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
  Card,
  Badge,
  SimpleGrid,
  Box,
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
import type { SkillCategory } from '@/generated/models/skillCategory';
import type { SkillExecutionMode } from '@/generated/models/skillExecutionMode';
import { EmptyState } from '@/shared/components/EmptyState';

interface Skill {
  skill_id: string;
  name: string;
  description: string;
  content: string;
  category: string;
  version: string;
  execution_mode: string;
}

const CATEGORY_OPTIONS = [
  { value: 'code_generation', label: 'Code Generation' },
  { value: 'code_analysis', label: 'Code Analysis' },
  { value: 'testing', label: 'Testing' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'devops', label: 'DevOps' },
  { value: 'security', label: 'Security' },
  { value: 'project_management', label: 'Project Management' },
  { value: 'design', label: 'Design' },
  { value: 'communication', label: 'Communication' },
  { value: 'data', label: 'Data' },
  { value: 'custom', label: 'Custom' },
];

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  CATEGORY_OPTIONS.map((c) => [c.value, c.label]),
);

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
      name: '',
      description: '',
      content: '',
      category: 'custom',
      version: '1.0.0',
      execution_mode: 'inline',
    },
    validate: {
      name: (v) => (v.trim() ? null : 'Required'),
    },
  });

  const editForm = useForm({
    initialValues: {
      name: '',
      description: '',
      content: '',
      category: 'custom',
      version: '',
      execution_mode: 'inline',
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const skills = (resp?.data ?? []) as unknown as Skill[];

  const handleCreate = createForm.onSubmit((values) => {
    registerMutation.mutate(
      { data: { ...values, category: values.category as SkillCategory, execution_mode: values.execution_mode as SkillExecutionMode, input_schema: {}, output_schema: {} } },
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
      category: skill.category ?? 'custom',
      version: skill.version,
      execution_mode: skill.execution_mode,
    });
  };

  const handleEdit = editForm.onSubmit((values) => {
    if (!editSkill) return;
    updateMutation.mutate(
      { skillId: editSkill.skill_id, data: { ...values, category: values.category as SkillCategory, execution_mode: values.execution_mode as SkillExecutionMode } },
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
        <Stack gap="lg">
          {Object.entries(
            skills.reduce<Record<string, Skill[]>>((acc, s) => {
              const cat = s.category || 'custom';
              (acc[cat] ??= []).push(s);
              return acc;
            }, {}),
          ).sort(([a], [b]) => (CATEGORY_LABELS[a] ?? a).localeCompare(CATEGORY_LABELS[b] ?? b))
           .map(([category, categorySkills]) => (
            <Box
              key={category}
              p="md"
              style={(theme) => ({
                border: `1px solid ${theme.colors.dark[4]}`,
                borderRadius: theme.radius.md,
              })}
            >
              <Text fw={600} size="sm" tt="uppercase" c="dimmed" mb="sm">
                {CATEGORY_LABELS[category] ?? category}
              </Text>
              <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                {categorySkills.map((s) => (
                  <Card
                    key={s.skill_id}
                    shadow="sm"
                    padding="lg"
                    radius="md"
                    withBorder
                    style={{ cursor: 'pointer' }}
                    onClick={() => openEdit(s)}
                  >
                    <Group justify="space-between" mb="xs">
                      <Text fw={600} size="lg">{s.name}</Text>
                      <Group gap={4}>
                        <ActionIcon variant="subtle" onClick={(e) => { e.stopPropagation(); openEdit(s); }}>
                          <IconEdit size={16} />
                        </ActionIcon>
                        <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(s.skill_id); }}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Group>
                    </Group>
                    <Text size="sm" c="dimmed" lineClamp={2} mb="md">
                      {s.description || 'No description'}
                    </Text>
                    <Group gap="xs">
                      <Badge variant="light" size="sm">v{s.version}</Badge>
                      <Badge variant="light" size="sm" color={s.execution_mode === 'sandbox' ? 'orange' : 'blue'}>
                        {s.execution_mode}
                      </Badge>
                    </Group>
                  </Card>
                ))}
              </SimpleGrid>
            </Box>
          ))}
        </Stack>
      )}

      {/* Create Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Register Skill" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="My Skill" {...createForm.getInputProps('name')} />
            <Textarea label="Description" placeholder="What this skill does" autosize minRows={2} {...createForm.getInputProps('description')} />
            <Textarea
              label="Content"
              placeholder="Skill content / prompt template (OpenSkill format)"
              autosize minRows={6}
              styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
              {...createForm.getInputProps('content')}
            />
            <Select
              label="Category"
              data={CATEGORY_OPTIONS}
              {...createForm.getInputProps('category')}
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
      <Modal opened={!!editSkill} onClose={() => setEditSkill(null)} title={`Edit Skill: ${editSkill?.name ?? ''}`} size="lg">
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
            <Select
              label="Category"
              data={CATEGORY_OPTIONS}
              {...editForm.getInputProps('category')}
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
