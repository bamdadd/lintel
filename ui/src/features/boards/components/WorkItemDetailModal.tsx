import { useState, useEffect } from 'react';
import {
  Modal,
  TextInput,
  Textarea,
  Select,
  Stack,
  Group,
  Button,
  Text,
  Badge,
  TagsInput,
  Divider,
  Anchor,
  Loader,
  ThemeIcon,
  TypographyStylesProvider,
  ActionIcon,
  Box,
  ScrollArea,
} from '@mantine/core';
import { IconProgress, IconGitBranch, IconExternalLink, IconPencil, IconArrowRight, IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '@/features/chat/chat-markdown.css';
import { notifications } from '@mantine/notifications';
import { useMediaQuery } from '@mantine/hooks';
import { useNavigate } from 'react-router';
import { useUpdateWorkItem, useDeleteWorkItem, usePipelinesForWorkItem } from '../api';
import type { WorkItem } from '../api';
import { useQueryClient } from '@tanstack/react-query';
import { StatusBadge } from '@/shared/components/StatusBadge';
import { usePipelineSSE } from '@/features/pipelines/hooks/usePipelineSSE';

const WORK_TYPES = [
  { value: 'task', label: 'Task' },
  { value: 'feature', label: 'Feature' },
  { value: 'bug', label: 'Bug' },
  { value: 'refactor', label: 'Refactor' },
];

const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'in_review', label: 'In Review' },
  { value: 'approved', label: 'Approved' },
  { value: 'merged', label: 'Merged' },
  { value: 'closed', label: 'Closed' },
];


interface BoardColumnDef {
  column_id: string;
  name: string;
  position: number;
  work_item_status: string;
}

interface WorkItemDetailModalProps {
  item: WorkItem | null;
  opened: boolean;
  onClose: () => void;
  columns?: BoardColumnDef[];
}

export function WorkItemDetailModal({ item, opened, onClose, columns }: WorkItemDetailModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [workType, setWorkType] = useState('task');
  const [status, setStatus] = useState('open');
  const [assignee, setAssignee] = useState('');
  const [tags, setTags] = useState<string[]>([]);

  const [editingDescription, setEditingDescription] = useState(false);
  const isMobile = useMediaQuery('(max-width: 768px)');
  const navigate = useNavigate();
  const updateMut = useUpdateWorkItem();
  const deleteMut = useDeleteWorkItem();
  const qc = useQueryClient();
  const { data: pipelines, isLoading: pipelinesLoading } = usePipelinesForWorkItem(
    item?.work_item_id,
  );

  // Subscribe to SSE for the latest non-terminal pipeline to get live status updates
  const activePipeline = pipelines?.find(
    (p) => !['succeeded', 'failed', 'cancelled', 'completed'].includes(p.status),
  );
  const { onUpdate } = usePipelineSSE(activePipeline?.run_id ?? null);
  onUpdate(() => {
    void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
  });

  useEffect(() => {
    if (item) {
      setTitle(item.title);
      setDescription(item.description);
      setWorkType(item.work_type);
      setStatus(item.status);
      setAssignee(item.assignee_agent_role);
      setTags(item.tags ?? []);
      setEditingDescription(false);
    }
  }, [item]);

  const handleSave = () => {
    if (!item) return;
    const data: Record<string, unknown> = {};
    if (title !== item.title) data.title = title;
    if (description !== item.description) data.description = description;
    if (workType !== item.work_type) data.work_type = workType;
    if (status !== item.status) data.status = status;
    if (assignee !== item.assignee_agent_role) data.assignee_agent_role = assignee;
    if (JSON.stringify(tags) !== JSON.stringify(item.tags ?? [])) data.tags = tags;

    if (Object.keys(data).length === 0) {
      onClose();
      return;
    }

    updateMut.mutate(
      { workItemId: item.work_item_id, data },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
          void qc.invalidateQueries({ queryKey: ['/api/v1/pipelines'] });
          notifications.show({ title: 'Saved', message: 'Work item updated', color: 'green' });
          onClose();
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to update', color: 'red' });
        },
      },
    );
  };

  if (!item) return null;

  const sorted = columns ? [...columns].sort((a, b) => a.position - b.position) : [];
  const currentIdx = sorted.findIndex((c) => c.work_item_status === status);
  const prevCol = currentIdx > 0 ? sorted[currentIdx - 1] : null;
  const nextCol = currentIdx >= 0 && currentIdx < sorted.length - 1 ? sorted[currentIdx + 1] : null;

  const handleMove = (col: BoardColumnDef) => {
    if (!item) return;
    const newStatus = col.work_item_status;
    setStatus(newStatus);
    updateMut.mutate(
      { workItemId: item.work_item_id, data: { status: newStatus, column_id: col.column_id } },
      {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
          notifications.show({ title: 'Moved', message: `Moved to ${col.name}`, color: 'green' });
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to move', color: 'red' });
        },
      },
    );
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Work Item Details" size="lg" fullScreen={isMobile}>
      <Stack gap="sm">
        <Group gap={8} wrap="wrap">
          <Badge size="xs" variant="light" color="dimmed">
            {item.work_item_id.slice(0, 8)}
          </Badge>
          <StatusBadge status={item.status} size="xs" />
        </Group>

        {/* ── Last pipeline status banner ──────────────────────────────── */}
        {pipelines && pipelines.length > 0 && (() => {
          const last = pipelines[0]!;
          return (
            <Button
              variant="light"
              size={isMobile ? 'sm' : 'md'}
              color={
                last.status === 'completed' ? 'green'
                  : last.status === 'failed' ? 'red'
                  : last.status === 'running' ? 'blue'
                  : 'gray'
              }
              fullWidth
              justify="space-between"
              rightSection={<IconArrowRight size={14} />}
              onClick={() => {
                onClose();
                navigate(`/pipelines/${last.run_id}`);
              }}
            >
              <Group gap="xs">
                <IconProgress size={14} />
                <Text size="sm">Pipeline {last.run_id.slice(0, 8)}</Text>
                <StatusBadge status={last.status} size="xs" />
              </Group>
            </Button>
          );
        })()}

        {/* ── Move to prev / next column ─────────────────────────────── */}
        {sorted.length > 1 && (
          <Group grow>
            <Button
              variant="light"
              color="gray"
              size={isMobile ? 'sm' : 'md'}
              leftSection={<IconChevronLeft size={16} />}
              disabled={!prevCol}
              onClick={() => prevCol && handleMove(prevCol)}
            >
              {prevCol ? prevCol.name : 'Back'}
            </Button>
            <Button
              variant="light"
              color="blue"
              size={isMobile ? 'sm' : 'md'}
              rightSection={<IconChevronRight size={16} />}
              disabled={!nextCol}
              onClick={() => nextCol && handleMove(nextCol)}
            >
              {nextCol ? nextCol.name : 'Next'}
            </Button>
          </Group>
        )}

        <TextInput label="Title" value={title} onChange={(e) => setTitle(e.currentTarget.value)} size={isMobile ? 'sm' : 'md'} />

        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" fw={500}>Description</Text>
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={() => setEditingDescription((v) => !v)}
              title={editingDescription ? 'Preview' : 'Edit'}
            >
              <IconPencil size={14} />
            </ActionIcon>
          </Group>
          {editingDescription ? (
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.currentTarget.value)}
              minRows={isMobile ? 4 : 6}
              autosize
              placeholder="Markdown supported..."
              size={isMobile ? 'sm' : 'md'}
            />
          ) : description ? (
            <Box
              p="sm"
              style={{
                border: '1px solid var(--mantine-color-dark-4)',
                borderRadius: 'var(--mantine-radius-sm)',
                cursor: 'pointer',
                maxHeight: isMobile ? 200 : undefined,
                overflow: isMobile ? 'auto' : undefined,
              }}
              onClick={() => setEditingDescription(true)}
            >
              <TypographyStylesProvider>
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {description}
                  </ReactMarkdown>
                </div>
              </TypographyStylesProvider>
            </Box>
          ) : (
            <Text
              size="sm"
              c="dimmed"
              p="sm"
              style={{
                border: '1px dashed var(--mantine-color-dark-4)',
                borderRadius: 'var(--mantine-radius-sm)',
                cursor: 'pointer',
              }}
              onClick={() => setEditingDescription(true)}
            >
              Click to add a description...
            </Text>
          )}
        </Box>
        <Group grow wrap={isMobile ? 'wrap' : 'nowrap'}>
          <Select label="Type" data={WORK_TYPES} value={workType} onChange={(v) => setWorkType(v ?? 'task')} size={isMobile ? 'sm' : 'md'} />
          <Select label="Status" data={STATUSES} value={status} onChange={(v) => setStatus(v ?? 'open')} size={isMobile ? 'sm' : 'md'} />
        </Group>
        <TextInput
          label="Assignee (agent role)"
          value={assignee}
          onChange={(e) => setAssignee(e.currentTarget.value)}
          placeholder="e.g. coder, reviewer"
          size={isMobile ? 'sm' : 'md'}
        />
        <TagsInput label="Tags" value={tags} onChange={setTags} placeholder="Add tags" size={isMobile ? 'sm' : 'md'} />

        {/* ── Actions ─────────────────────────────────────────────────── */}
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Button
            color="red"
            variant="subtle"
            size={isMobile ? 'xs' : 'sm'}
            onClick={() => {
              if (!item || !window.confirm('Delete this work item?')) return;
              deleteMut.mutate(item.work_item_id, {
                onSuccess: () => {
                  void qc.invalidateQueries({ queryKey: ['/api/v1/work-items'] });
                  notifications.show({ title: 'Deleted', message: 'Work item removed', color: 'green' });
                  onClose();
                },
                onError: () => {
                  notifications.show({ title: 'Error', message: 'Failed to delete', color: 'red' });
                },
              });
            }}
            loading={deleteMut.isPending}
          >
            Delete
          </Button>
          <Group gap="xs">
            <Button variant="default" onClick={onClose} size={isMobile ? 'sm' : 'md'}>
              Cancel
            </Button>
            <Button onClick={handleSave} loading={updateMut.isPending} size={isMobile ? 'sm' : 'md'}>
              Save
            </Button>
          </Group>
        </Group>

        <Divider label="Linked Resources" labelPosition="left" mt="sm" />

        {item.branch_name && (
          <Group gap="xs" wrap="wrap" style={{ overflow: 'hidden' }}>
            <ThemeIcon size="sm" variant="light" color="gray">
              <IconGitBranch size={14} />
            </ThemeIcon>
            <Text size="xs" style={{ wordBreak: 'break-all' }}>
              Branch: <Text span fw={500}>{item.branch_name}</Text>
            </Text>
          </Group>
        )}

        {item.pr_url && (
          <Group gap="xs">
            <ThemeIcon size="sm" variant="light" color="blue">
              <IconExternalLink size={14} />
            </ThemeIcon>
            <Anchor href={item.pr_url} target="_blank" size="sm" style={{ wordBreak: 'break-all' }}>
              Pull Request
            </Anchor>
          </Group>
        )}

        {item.thread_ref_str && (
          <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
            Thread: {item.thread_ref_str}
          </Text>
        )}

        <Text size="sm" fw={500} mt="xs">
          <Group gap={6}>
            <ThemeIcon size="sm" variant="light" color="violet">
              <IconProgress size={14} />
            </ThemeIcon>
            Pipelines
          </Group>
        </Text>

        {pipelinesLoading ? (
          <Loader size="sm" />
        ) : !pipelines || pipelines.length === 0 ? (
          <Text size="xs" c="dimmed">
            No pipelines linked. Moving to &quot;In Progress&quot; will trigger a workflow.
          </Text>
        ) : isMobile ? (
          /* Mobile: card layout instead of table */
          <Stack gap="xs">
            {pipelines.map((p) => (
              <Anchor key={p.run_id} href={`/pipelines/${p.run_id}`} underline="never">
                <Box p="xs" style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 'var(--mantine-radius-sm)' }}>
                  <Group justify="space-between" wrap="wrap" gap={4}>
                    <Text size="xs" fw={500}>{p.run_id.slice(0, 8)}</Text>
                    <StatusBadge status={p.status} size="xs" />
                  </Group>
                  <Text size="xs" c="dimmed" mt={2}>{p.created_at ? new Date(p.created_at).toLocaleString() : '—'}</Text>
                </Box>
              </Anchor>
            ))}
          </Stack>
        ) : (
          <ScrollArea type="auto">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 12 }}>Run ID</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 12 }}>Workflow</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 12 }}>Status</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 12 }}>Created</th>
                </tr>
              </thead>
              <tbody>
                {pipelines.map((p) => (
                  <tr key={p.run_id}>
                    <td style={{ padding: '6px 8px' }}>
                      <Anchor href={`/pipelines/${p.run_id}`} size="xs">
                        {p.run_id.slice(0, 8)}
                      </Anchor>
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      <Text size="xs">{p.workflow_definition_id}</Text>
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      <StatusBadge status={p.status} size="xs" />
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      <Text size="xs" c="dimmed">
                        {p.created_at ? new Date(p.created_at).toLocaleString() : '—'}
                      </Text>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        )}
      </Stack>
    </Modal>
  );
}
