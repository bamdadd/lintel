import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select,
  Loader, Center, ActionIcon, Badge, Textarea, MultiSelect,
  Card, Text, SimpleGrid, ThemeIcon, Checkbox,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconShieldCheck, IconPlus } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { regulationHooks, useRegulationTemplates, useAddRegulationFromTemplate } from '../api';
import { EmptyState } from '@/shared/components/EmptyState';

interface RegulationItem {
  regulation_id: string;
  project_id: string;
  name: string;
  description: string;
  authority: string;
  reference_url: string;
  version: string;
  status: string;
  risk_level: string;
  tags: string[];
}

interface ProjectItem { project_id: string; name: string; }

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'deprecated', label: 'Deprecated' },
  { value: 'non_compliant', label: 'Non-Compliant' },
];

const RISK_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

const riskColor: Record<string, string> = { low: 'green', medium: 'yellow', high: 'orange', critical: 'red' };
const statusColor: Record<string, string> = { draft: 'gray', active: 'green', under_review: 'yellow', deprecated: 'orange', non_compliant: 'red' };

const WELL_KNOWN_REGULATIONS = [
  'HIPAA', 'GDPR', 'IEC 62304', 'ISO 14971', 'ISO 13485',
  'FDA 21 CFR Part 11', 'FDA 21 CFR Part 820', 'SOC 2', 'ISO 27001',
  'IEC 62443', 'MDR 2017/745', 'IVDR 2017/746',
];

export function Component() {
  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as unknown as ProjectItem[];
  const [filterProject, setFilterProject] = useState<string>('');

  const { data: resp, isLoading } = regulationHooks.useList(filterProject || undefined);
  const { data: templatesResp } = useRegulationTemplates();
  const createMut = regulationHooks.useCreate();
  const updateMut = regulationHooks.useUpdate();
  const removeMut = regulationHooks.useRemove();
  const addFromTemplate = useAddRegulationFromTemplate();
  const [creating, setCreating] = useState(false);
  const [editItem, setEditItem] = useState<RegulationItem | null>(null);
  const [browsingTemplates, setBrowsingTemplates] = useState(false);
  const [templateProject, setTemplateProject] = useState<string>('');

  const templates = (templatesResp?.data ?? []) as unknown as RegulationItem[];

  const projectOptions = [{ value: '', label: 'All Projects' }, ...projects.map((p) => ({ value: p.project_id, label: p.name }))];
  const projectRequired = projects.map((p) => ({ value: p.project_id, label: p.name }));

  const form = useForm({
    initialValues: {
      name: '', project_id: '', description: '', authority: '',
      reference_url: '', version: '', status: 'active', risk_level: 'medium', tags: [] as string[],
    },
    validate: { name: (v) => (v.trim() ? null : 'Required'), project_id: (v) => (v ? null : 'Required') },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', authority: '', reference_url: '',
      version: '', status: 'active', risk_level: 'medium', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const items = (resp?.data ?? []) as unknown as RegulationItem[];

  const handleCreate = form.onSubmit((values) => {
    createMut.mutate(values as any, {
      onSuccess: () => {
        notifications.show({ title: 'Created', message: 'Regulation added', color: 'green' });
        form.reset();
        setCreating(false);
      },
      onError: () => notifications.show({ title: 'Error', message: 'Failed to create', color: 'red' }),
    });
  });

  const openEdit = (item: RegulationItem) => {
    setEditItem(item);
    editForm.setValues({
      name: item.name, description: item.description, authority: item.authority,
      reference_url: item.reference_url, version: item.version,
      status: item.status, risk_level: item.risk_level, tags: item.tags ?? [],
    });
  };

  const handleUpdate = editForm.onSubmit((values) => {
    if (!editItem) return;
    updateMut.mutate({ id: editItem.regulation_id, data: values as any }, {
      onSuccess: () => {
        notifications.show({ title: 'Updated', message: 'Regulation updated', color: 'green' });
        setEditItem(null);
      },
    });
  });

  const handleDelete = (id: string) => {
    removeMut.mutate(id, {
      onSuccess: () => {
        notifications.show({ title: 'Deleted', message: 'Regulation removed', color: 'orange' });
        if (editItem?.regulation_id === id) setEditItem(null);
      },
    });
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Regulations</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button variant="light" onClick={() => setBrowsingTemplates(true)} leftSection={<IconShieldCheck size={16} />}>Browse Templates</Button>
          <Button onClick={() => setCreating(true)}>Add Regulation</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No regulations" description="Add regulations like HIPAA, GDPR, or IEC 62304 to track compliance" actionLabel="Add Regulation" onAction={() => setCreating(true)} />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Authority</Table.Th>
              <Table.Th>Risk</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Version</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={item.regulation_id} style={{ cursor: 'pointer' }} onClick={() => openEdit(item)}>
                <Table.Td fw={500}>{item.name}</Table.Td>
                <Table.Td>{item.authority || '—'}</Table.Td>
                <Table.Td><Badge color={riskColor[item.risk_level]} variant="dot" size="sm">{item.risk_level}</Badge></Table.Td>
                <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                <Table.Td>{item.version || '—'}</Table.Td>
                <Table.Td>
                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(item.regulation_id); }}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {/* Create modal */}
      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Regulation" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <Select label="Name" data={WELL_KNOWN_REGULATIONS.map((r) => ({ value: r, label: r }))} searchable creatable getCreateLabel={(v) => `Custom: ${v}`} onCreate={(v) => { form.setFieldValue('name', v); return v; }} {...form.getInputProps('name')} />
            <Select label="Project" data={projectRequired} searchable {...form.getInputProps('project_id')} />
            <Textarea label="Description" autosize minRows={2} {...form.getInputProps('description')} />
            <TextInput label="Authority" placeholder="e.g. EU, FDA, ISO" {...form.getInputProps('authority')} />
            <TextInput label="Reference URL" placeholder="https://..." {...form.getInputProps('reference_url')} />
            <TextInput label="Version" {...form.getInputProps('version')} />
            <Group grow>
              <Select label="Risk Level" data={RISK_OPTIONS} {...form.getInputProps('risk_level')} />
              <Select label="Status" data={STATUS_OPTIONS} {...form.getInputProps('status')} />
            </Group>
            <Button type="submit" loading={createMut.isPending}>Create</Button>
          </Stack>
        </form>
      </Modal>

      {/* Template browser modal */}
      <Modal opened={browsingTemplates} onClose={() => setBrowsingTemplates(false)} title="Regulation Templates" size="xl">
        <Stack gap="md">
          <Select label="Add to project" placeholder="Select a project" data={projectRequired} value={templateProject} onChange={(v) => setTemplateProject(v ?? '')} searchable />
          {(['Healthcare & Medical Device', 'Data Protection', 'Financial (UK)', 'Information Security', 'AI Regulation'] as const).map((category) => {
            const tagMap: Record<string, string[]> = {
              'Healthcare & Medical Device': ['medical-device', 'health', 'samd'],
              'Data Protection': ['data-protection', 'privacy'],
              'Financial (UK)': ['financial'],
              'Information Security': ['security'],
              'AI Regulation': ['ai'],
            };
            const catTags = tagMap[category];
            const catTemplates = templates.filter((t) => (t.tags ?? []).some((tag) => catTags.includes(tag)));
            if (catTemplates.length === 0) return null;
            const existingNames = new Set(items.map((i) => i.name));
            return (
              <div key={category}>
                <Text fw={700} size="sm" mb="xs" tt="uppercase" c="dimmed">{category}</Text>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>
                  {catTemplates.map((tmpl) => {
                    const alreadyAdded = existingNames.has(tmpl.name);
                    return (
                      <Card key={tmpl.regulation_id} withBorder padding="sm" radius="md">
                        <Group justify="space-between" mb={4}>
                          <Group gap="xs">
                            <ThemeIcon size="sm" color={riskColor[tmpl.risk_level]} variant="light"><IconShieldCheck size={14} /></ThemeIcon>
                            <Text fw={600} size="sm">{tmpl.name}</Text>
                          </Group>
                          <Badge color={riskColor[tmpl.risk_level]} variant="dot" size="xs">{tmpl.risk_level}</Badge>
                        </Group>
                        <Text size="xs" c="dimmed" lineClamp={2} mb="xs">{tmpl.description}</Text>
                        <Group justify="space-between">
                          <Text size="xs" c="dimmed">{tmpl.authority}</Text>
                          <Button
                            size="xs"
                            variant="light"
                            leftSection={<IconPlus size={12} />}
                            disabled={!templateProject || alreadyAdded}
                            loading={addFromTemplate.isPending}
                            onClick={() => {
                              addFromTemplate.mutate({ template_id: tmpl.regulation_id, project_id: templateProject } as any, {
                                onSuccess: () => {
                                  notifications.show({ title: 'Added', message: `${tmpl.name} added to project`, color: 'green' });
                                },
                              });
                            }}
                          >
                            {alreadyAdded ? 'Added' : 'Add'}
                          </Button>
                        </Group>
                      </Card>
                    );
                  })}
                </SimpleGrid>
              </div>
            );
          })}
        </Stack>
      </Modal>

      {/* Edit modal */}
      <Modal opened={!!editItem} onClose={() => setEditItem(null)} title={`Edit: ${editItem?.name ?? ''}`} size="lg">
        <form onSubmit={handleUpdate}>
          <Stack gap="sm">
            <TextInput label="Name" {...editForm.getInputProps('name')} />
            <Textarea label="Description" autosize minRows={2} {...editForm.getInputProps('description')} />
            <TextInput label="Authority" {...editForm.getInputProps('authority')} />
            <TextInput label="Reference URL" {...editForm.getInputProps('reference_url')} />
            <TextInput label="Version" {...editForm.getInputProps('version')} />
            <Group grow>
              <Select label="Risk Level" data={RISK_OPTIONS} {...editForm.getInputProps('risk_level')} />
              <Select label="Status" data={STATUS_OPTIONS} {...editForm.getInputProps('status')} />
            </Group>
            <Button type="submit" loading={updateMut.isPending}>Save</Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
