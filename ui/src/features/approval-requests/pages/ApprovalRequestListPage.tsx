import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Loader, Center, Badge, Text,
  Modal, TextInput, Textarea, Paper, Anchor, Spoiler, TypographyStylesProvider,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconPlayerPlay, IconArrowRight } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { PlanView } from '@/features/pipelines/components/PlanView';
import {
  useApprovalRequestsListApprovalRequests,
  useApprovalRequestsApproveApprovalRequest,
  useApprovalRequestsRejectApprovalRequest,
} from '@/generated/api/approval-requests/approval-requests';
import { usePipelinesGetPipeline, usePipelinesListStages } from '@/generated/api/pipelines/pipelines';
import { EmptyState } from '@/shared/components/EmptyState';
import { TimeAgo } from '@/shared/components/TimeAgo';

interface ApprovalItem {
  approval_id: string;
  run_id: string;
  gate_type: string;
  requested_by: string;
  status: string;
  decided_by: string;
  reason: string;
  expires_at: string;
  created_at: string;
  decided_at: string;
}

const statusColor: Record<string, string> = { pending: 'yellow', approved: 'green', rejected: 'red', expired: 'gray' };

const GATE_LABELS: Record<string, { label: string; description: string }> = {
  approval_gate_research: { label: 'Research Review', description: 'Review the research findings before planning begins' },
  approve_research: { label: 'Research Review', description: 'Review the research findings before planning begins' },
  approval_gate_spec: { label: 'Spec Review', description: 'Review the implementation plan before coding begins' },
  approve_spec: { label: 'Spec Review', description: 'Review the implementation plan before coding begins' },
  approval_gate_merge: { label: 'Merge Approval', description: 'Approve the final changes for merge into the target branch' },
  approve_merge: { label: 'Merge Approval', description: 'Approve the final changes for merge into the target branch' },
  spec_approval: { label: 'Spec Review', description: 'Review the implementation plan before coding begins' },
  merge_approval: { label: 'Merge Approval', description: 'Approve the final changes for merge' },
};

/** Inline preview of the stage content that precedes this gate. */
function StagePreview({ runId, gateType }: { runId: string; gateType: string }) {
  const { data: stagesResp } = usePipelinesListStages(runId, { query: { enabled: !!runId } });
  const stages = (stagesResp?.data ?? []) as Array<{
    name: string;
    stage_type: string;
    status: string;
    outputs?: Record<string, unknown>;
  }>;

  // Find the content stage that precedes this approval gate
  const isResearch = gateType.includes('research');
  const isPlan = gateType.includes('spec') || gateType.includes('plan');

  if (isResearch) {
    const stage = stages.find((s) => s.name === 'research' || s.stage_type === 'research');
    const content = stage?.outputs?.research_report as string | undefined;
    if (!content) return null;
    return (
      <Paper p="sm" bg="var(--mantine-color-dark-7)" radius="sm" mt="xs">
        <Spoiler maxHeight={120} showLabel="Show more" hideLabel="Show less">
          <TypographyStylesProvider>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{content}</Text>
          </TypographyStylesProvider>
        </Spoiler>
      </Paper>
    );
  }

  if (isPlan) {
    const stage = stages.find((s) => s.name === 'plan' || s.stage_type === 'plan');
    const plan = stage?.outputs?.plan;
    if (!plan) return null;
    return (
      <Paper p="sm" bg="var(--mantine-color-dark-7)" radius="sm" mt="xs">
        <Spoiler maxHeight={200} showLabel="Show more" hideLabel="Show less">
          <PlanView plan={plan as Record<string, unknown> | string} />
        </Spoiler>
      </Paper>
    );
  }

  return null;
}

/** Pipeline context badge for an approval. */
function PipelineLink({ runId }: { runId: string }) {
  const navigate = useNavigate();
  const { data: pipelineResp } = usePipelinesGetPipeline(runId, { query: { enabled: !!runId } });
  const pipeline = (pipelineResp?.data ?? {}) as Record<string, unknown>;
  const pipelineStatus = pipeline.status as string | undefined;

  return (
    <Group gap="xs" wrap="nowrap">
      <Anchor
        size="sm"
        onClick={(e: React.MouseEvent) => { e.stopPropagation(); navigate(`/pipelines/${runId}`); }}
        style={{ cursor: 'pointer' }}
      >
        <Group gap={4} wrap="nowrap">
          <IconPlayerPlay size={14} />
          <Text size="xs" span>{runId.slice(0, 8)}</Text>
        </Group>
      </Anchor>
      {pipelineStatus && (
        <Badge size="xs" variant="dot" color={pipelineStatus === 'waiting_approval' ? 'yellow' : pipelineStatus === 'completed' ? 'green' : 'gray'}>
          {pipelineStatus.replace('_', ' ')}
        </Badge>
      )}
    </Group>
  );
}

export function Component() {
  const { data: resp, isLoading } = useApprovalRequestsListApprovalRequests();
  const approveMut = useApprovalRequestsApproveApprovalRequest();
  const rejectMut = useApprovalRequestsRejectApprovalRequest();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [rejectModal, setRejectModal] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [decidedBy, setDecidedBy] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  const approvals = (resp?.data ?? []) as ApprovalItem[];
  const pending = approvals.filter((a) => a.status === 'pending');
  const resolved = approvals.filter((a) => a.status !== 'pending');

  const handleApprove = (id: string) => {
    approveMut.mutate(
      { approvalId: id, data: { decided_by: decidedBy || 'admin' } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Approved', message: 'Request approved', color: 'green' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/approval-requests'] });
        },
        onError: () => notifications.show({ title: 'Error', message: 'Failed to approve', color: 'red' }),
      },
    );
  };

  const handleReject = () => {
    if (!rejectModal) return;
    rejectMut.mutate(
      { approvalId: rejectModal, data: { decided_by: decidedBy || 'admin', reason: rejectReason } },
      {
        onSuccess: () => {
          notifications.show({ title: 'Rejected', message: 'Request rejected', color: 'orange' });
          void qc.invalidateQueries({ queryKey: ['/api/v1/approval-requests'] });
          setRejectModal(null); setRejectReason('');
        },
      },
    );
  };

  const gateInfo = (gate: string) => GATE_LABELS[gate] ?? { label: gate, description: '' };

  return (
    <Stack gap="md">
      <Title order={2}>Approval Requests</Title>

      {approvals.length === 0 ? (
        <EmptyState title="No approval requests" description="Approval requests appear when policies require human review" />
      ) : (
        <>
          {pending.length > 0 && (
            <Stack gap="xs">
              <Title order={4}>Pending ({pending.length})</Title>
              {pending.map((a) => {
                const gate = gateInfo(a.gate_type);
                const isExpanded = expandedId === a.approval_id;
                return (
                  <Paper key={a.approval_id} withBorder p="md">
                    <Stack gap="sm">
                      <Group justify="space-between" wrap="nowrap">
                        <Stack gap={2}>
                          <Group gap="xs">
                            <Text fw={600} size="sm">{gate.label}</Text>
                            <Badge variant="light" color="yellow" size="sm">Pending</Badge>
                          </Group>
                          {gate.description && <Text size="xs" c="dimmed">{gate.description}</Text>}
                        </Stack>
                        <Group gap="xs" wrap="nowrap">
                          <Button size="xs" color="green" onClick={() => handleApprove(a.approval_id)} loading={approveMut.isPending}>Approve</Button>
                          <Button size="xs" color="red" variant="light" onClick={() => setRejectModal(a.approval_id)}>Reject</Button>
                        </Group>
                      </Group>

                      <Group gap="md">
                        <PipelineLink runId={a.run_id} />
                        {a.requested_by && <Text size="xs" c="dimmed">Requested by: {a.requested_by}</Text>}
                        {a.expires_at && <Group gap={4} wrap="nowrap"><Text size="xs" c="dimmed">Expires:</Text><TimeAgo date={a.expires_at} size="xs" c="dimmed" /></Group>}
                      </Group>

                      <Group gap="xs">
                        <Anchor
                          size="xs"
                          onClick={() => setExpandedId(isExpanded ? null : a.approval_id)}
                          style={{ cursor: 'pointer' }}
                        >
                          {isExpanded ? 'Hide content' : 'Preview content'}
                          <IconArrowRight size={12} style={{ marginLeft: 4, verticalAlign: 'middle' }} />
                        </Anchor>
                        <Anchor size="xs" onClick={() => navigate(`/pipelines/${a.run_id}`)}>
                          Open in pipeline
                        </Anchor>
                      </Group>

                      {isExpanded && <StagePreview runId={a.run_id} gateType={a.gate_type} />}
                    </Stack>
                  </Paper>
                );
              })}
            </Stack>
          )}

          {resolved.length > 0 && (
            <>
              <Title order={4}>Resolved ({resolved.length})</Title>
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Gate</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Pipeline</Table.Th>
                    <Table.Th>Decided By</Table.Th>
                    <Table.Th>Reason</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {resolved.map((a) => {
                    const gate = gateInfo(a.gate_type);
                    return (
                      <Table.Tr key={a.approval_id}>
                        <Table.Td><Text size="sm">{gate.label}</Text></Table.Td>
                        <Table.Td><Badge color={statusColor[a.status] ?? 'gray'}>{a.status}</Badge></Table.Td>
                        <Table.Td><PipelineLink runId={a.run_id} /></Table.Td>
                        <Table.Td>{a.decided_by || '—'}</Table.Td>
                        <Table.Td><Text size="sm" lineClamp={1}>{a.reason || '—'}</Text></Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </>
          )}
        </>
      )}

      <Modal opened={!!rejectModal} onClose={() => setRejectModal(null)} title="Reject Request">
        <Stack gap="sm">
          <TextInput label="Your Name" value={decidedBy} onChange={(e) => setDecidedBy(e.currentTarget.value)} placeholder="admin" />
          <Textarea label="Reason" value={rejectReason} onChange={(e) => setRejectReason(e.currentTarget.value)} placeholder="Why is this being rejected?" />
          <Button color="red" onClick={handleReject} loading={rejectMut.isPending}>Reject</Button>
        </Stack>
      </Modal>
    </Stack>
  );
}
