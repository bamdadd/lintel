import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Modal, TextInput, Select, Checkbox,
  Loader, Center, ActionIcon, Badge, Textarea, Collapse, Anchor,
  Card, Text, SimpleGrid, ThemeIcon, Box, UnstyledButton,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconTrash, IconShieldCheck, IconPlus, IconChevronDown, IconChevronRight, IconPencil, IconExternalLink } from '@tabler/icons-react';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
import { regulationHooks, useRegulationTemplates, useAddRegulationFromTemplate, useGeneratePolicies } from '../api';
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

const CATEGORIES: { label: string; matchTags: string[] }[] = [
  { label: 'Healthcare & Medical Device', matchTags: ['medical-device', 'health', 'samd', 'diagnostics'] },
  { label: 'Data Protection & Privacy', matchTags: ['data-protection', 'privacy'] },
  { label: 'Financial', matchTags: ['financial', 'payments', 'aml', 'kyc'] },
  { label: 'Information Security', matchTags: ['security'] },
  { label: 'AI Regulation', matchTags: ['ai'] },
];

function categorise(items: RegulationItem[]): { label: string; items: RegulationItem[] }[] {
  const assigned = new Set<string>();
  const groups: { label: string; items: RegulationItem[] }[] = [];

  for (const cat of CATEGORIES) {
    const matched = items.filter(
      (item) => (item.tags ?? []).some((tag) => cat.matchTags.includes(tag)),
    );
    for (const m of matched) assigned.add(m.regulation_id);
    if (matched.length > 0) groups.push({ label: cat.label, items: matched });
  }

  const uncategorised = items.filter((item) => !assigned.has(item.regulation_id));
  if (uncategorised.length > 0) groups.push({ label: 'Other', items: uncategorised });

  return groups;
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Group gap="xs" align="flex-start">
      <Text size="sm" fw={600} w={120} style={{ flexShrink: 0 }}>{label}</Text>
      <Box style={{ flex: 1 }}>{children}</Box>
    </Group>
  );
}

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
  const generateMut = useGeneratePolicies();
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selectedRegulations, setSelectedRegulations] = useState<Set<string>>(new Set());
  const [editItem, setEditItem] = useState<RegulationItem | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
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

  const generateForm = useForm({
    initialValues: { industry_context: 'general', additional_context: '' },
  });

  const editForm = useForm({
    initialValues: {
      name: '', description: '', authority: '', reference_url: '',
      version: '', status: 'active', risk_level: 'medium', tags: [] as string[],
    },
  });

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const items = (resp?.data ?? []) as unknown as RegulationItem[];
  const groups = categorise(items);

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
        if (expandedId === id) setExpandedId(null);
      },
    });
  };

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const toggleCategory = (label: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const projectName = (projectId: string) => projects.find((p) => p.project_id === projectId)?.name ?? projectId;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Regulations</Title>
        <Group>
          <Select placeholder="Filter by project" data={projectOptions} value={filterProject} onChange={(v) => setFilterProject(v ?? '')} searchable clearable w={220} />
          <Button variant="light" onClick={() => setBrowsingTemplates(true)} leftSection={<IconShieldCheck size={16} />}>Browse Templates</Button>
          <Button variant="light" color="teal" disabled={selectedRegulations.size === 0} onClick={() => setGenerating(true)} leftSection={<IconShieldCheck size={16} />}>Generate Policies ({selectedRegulations.size})</Button>
          <Button onClick={() => setCreating(true)}>Add Regulation</Button>
        </Group>
      </Group>

      {items.length === 0 ? (
        <EmptyState title="No regulations" description="Add regulations like HIPAA, GDPR, or IEC 62304 to track compliance" actionLabel="Add Regulation" onAction={() => setCreating(true)} />
      ) : (
        <Stack gap="sm">
          {groups.map((group) => {
            const isCategoryCollapsed = collapsedCategories.has(group.label);
            return (
              <Box key={group.label}>
                <UnstyledButton onClick={() => toggleCategory(group.label)} w="100%">
                  <Group gap="xs" py="xs" px="sm" style={{ borderRadius: 'var(--mantine-radius-sm)' }} bg="var(--mantine-color-dark-6)">
                    {isCategoryCollapsed ? <IconChevronRight size={16} /> : <IconChevronDown size={16} />}
                    <Text fw={700} size="sm" tt="uppercase">{group.label}</Text>
                    <Badge size="xs" variant="filled" color="gray" circle>{group.items.length}</Badge>
                  </Group>
                </UnstyledButton>
                <Collapse in={!isCategoryCollapsed}>
                  <Table striped highlightOnHover mt={4}>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th w={30} />
                        <Table.Th>Name</Table.Th>
                        <Table.Th>Authority</Table.Th>
                        <Table.Th>Risk</Table.Th>
                        <Table.Th>Status</Table.Th>
                        <Table.Th>Version</Table.Th>
                        <Table.Th />
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {group.items.map((item) => {
                        const isExpanded = expandedId === item.regulation_id;
                        return (
                          <>
                            <Table.Tr key={item.regulation_id} style={{ cursor: 'pointer' }} onClick={() => toggleExpand(item.regulation_id)}>
                              <Table.Td>
                                <Group gap={4} wrap="nowrap">
                                  <Checkbox
                                    size="xs"
                                    checked={selectedRegulations.has(item.regulation_id)}
                                    onChange={(e) => {
                                      e.stopPropagation();
                                      setSelectedRegulations((prev) => {
                                        const next = new Set(prev);
                                        if (next.has(item.regulation_id)) next.delete(item.regulation_id);
                                        else next.add(item.regulation_id);
                                        return next;
                                      });
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  {isExpanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
                                </Group>
                              </Table.Td>
                              <Table.Td fw={500}>{item.name}</Table.Td>
                              <Table.Td>{item.authority || '—'}</Table.Td>
                              <Table.Td><Badge color={riskColor[item.risk_level]} variant="dot" size="sm">{item.risk_level}</Badge></Table.Td>
                              <Table.Td><Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge></Table.Td>
                              <Table.Td>{item.version || '—'}</Table.Td>
                              <Table.Td>
                                <Group gap={4}>
                                  <ActionIcon variant="subtle" onClick={(e) => { e.stopPropagation(); openEdit(item); }}>
                                    <IconPencil size={16} />
                                  </ActionIcon>
                                  <ActionIcon color="red" variant="subtle" onClick={(e) => { e.stopPropagation(); handleDelete(item.regulation_id); }}>
                                    <IconTrash size={16} />
                                  </ActionIcon>
                                </Group>
                              </Table.Td>
                            </Table.Tr>
                            {isExpanded && (
                              <Table.Tr key={`${item.regulation_id}-detail`}>
                                <Table.Td colSpan={7} p={0}>
                                  <Box px="lg" py="md" bg="var(--mantine-color-dark-7)">
                                    <Stack gap="xs">
                                      {item.description && (
                                        <DetailRow label="Description">
                                          <Text size="sm">{item.description}</Text>
                                        </DetailRow>
                                      )}
                                      <DetailRow label="Project">
                                        <Text size="sm">{projectName(item.project_id)}</Text>
                                      </DetailRow>
                                      <DetailRow label="Authority">
                                        <Text size="sm">{item.authority || '—'}</Text>
                                      </DetailRow>
                                      <DetailRow label="Version">
                                        <Text size="sm">{item.version || '—'}</Text>
                                      </DetailRow>
                                      <DetailRow label="Risk Level">
                                        <Badge color={riskColor[item.risk_level]} variant="filled" size="sm">{item.risk_level}</Badge>
                                      </DetailRow>
                                      <DetailRow label="Status">
                                        <Badge color={statusColor[item.status]} variant="light" size="sm">{item.status}</Badge>
                                      </DetailRow>
                                      {item.reference_url && (
                                        <DetailRow label="Reference">
                                          <Anchor href={item.reference_url} target="_blank" size="sm">
                                            <Group gap={4}>
                                              {item.reference_url}
                                              <IconExternalLink size={14} />
                                            </Group>
                                          </Anchor>
                                        </DetailRow>
                                      )}
                                      {item.tags && item.tags.length > 0 && (
                                        <DetailRow label="Tags">
                                          <Group gap={4}>
                                            {item.tags.map((tag) => (
                                              <Badge key={tag} variant="outline" size="xs">{tag}</Badge>
                                            ))}
                                          </Group>
                                        </DetailRow>
                                      )}
                                      <DetailRow label="ID">
                                        <Text size="xs" c="dimmed" ff="monospace">{item.regulation_id}</Text>
                                      </DetailRow>
                                    </Stack>
                                  </Box>
                                </Table.Td>
                              </Table.Tr>
                            )}
                          </>
                        );
                      })}
                    </Table.Tbody>
                  </Table>
                </Collapse>
              </Box>
            );
          })}
        </Stack>
      )}

      {/* Create modal */}
      <Modal opened={creating} onClose={() => setCreating(false)} title="Add Regulation" size="lg">
        <form onSubmit={handleCreate}>
          <Stack gap="sm">
            <TextInput label="Name" placeholder="e.g. HIPAA, GDPR, IEC 62304" {...form.getInputProps('name')} />
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
            const catTags = tagMap[category] ?? [];
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

      {/* Generate policies modal */}
      <Modal opened={generating} onClose={() => setGenerating(false)} title="Generate Policies" size="md">
        <form onSubmit={generateForm.onSubmit((values) => {
          const regIds = [...selectedRegulations];
          const projectId = items.find((i) => regIds.includes(i.regulation_id))?.project_id ?? '';
          if (!projectId) {
            notifications.show({ title: 'Error', message: 'Could not determine project', color: 'red' });
            return;
          }
          generateMut.mutate(
            { project_id: projectId, regulation_ids: regIds, ...values },
            {
              onSuccess: () => {
                notifications.show({ title: 'Started', message: 'Policy generation workflow started', color: 'green' });
                setGenerating(false);
                setSelectedRegulations(new Set());
                generateForm.reset();
              },
              onError: () => notifications.show({ title: 'Error', message: 'Failed to start generation', color: 'red' }),
            },
          );
        })}>
          <Stack gap="sm">
            <Text size="sm" c="dimmed">
              Generating policies for {selectedRegulations.size} regulation{selectedRegulations.size > 1 ? 's' : ''}:
            </Text>
            <Stack gap={4}>
              {[...selectedRegulations].map((id) => {
                const reg = items.find((i) => i.regulation_id === id);
                return <Badge key={id} variant="light" size="sm">{reg?.name ?? id}</Badge>;
              })}
            </Stack>
            <Select
              label="Industry Context"
              data={[
                { value: 'general', label: 'General' },
                { value: 'it', label: 'IT / Software' },
                { value: 'health', label: 'Healthcare' },
                { value: 'finance', label: 'Finance' },
              ]}
              {...generateForm.getInputProps('industry_context')}
            />
            <Textarea
              label="Additional Context"
              placeholder="Optional instructions, scope, or context for the AI..."
              autosize
              minRows={3}
              maxRows={8}
              {...generateForm.getInputProps('additional_context')}
            />
            <Button type="submit" color="teal" loading={generateMut.isPending}>Generate Policies</Button>
          </Stack>
        </form>
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
