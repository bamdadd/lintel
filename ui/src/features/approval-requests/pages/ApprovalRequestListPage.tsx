import { useState } from 'react';
import {
  Title, Stack, Table, Button, Group, Loader, Center, Badge, Text,
  Modal, TextInput, Textarea,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useApprovalRequestsListApprovalRequests,
  useApprovalRequestsApproveApprovalRequest,
  useApprovalRequestsRejectApprovalRequest,
} from '@/generated/api/approval-requests/approval-requests';
import { EmptyState } from '@/shared/components/EmptyState';

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

export function Component() {
  const { data: resp, isLoading } = useApprovalRequestsListApprovalRequests();
  const approveMut = useApprovalRequestsApproveApprovalRequest();
  const rejectMut = useApprovalRequestsRejectApprovalRequest();
  const qc = useQueryClient();
  const [rejectModal, setRejectModal] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [decidedBy, setDecidedBy] = useState('');

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

  return (
    <Stack gap="md">
      <Title order={2}>Approval Requests</Title>

      {approvals.length === 0 ? (
        <EmptyState title="No approval requests" description="Approval requests appear when policies require human review" />
      ) : (
        <>
          {pending.length > 0 && (
            <>
              <Title order={4}>Pending ({pending.length})</Title>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Gate</Table.Th>
                    <Table.Th>Requested By</Table.Th>
                    <Table.Th>Run</Table.Th>
                    <Table.Th>Expires</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {pending.map((a) => (
                    <Table.Tr key={a.approval_id}>
                      <Table.Td><Badge variant="light">{a.gate_type}</Badge></Table.Td>
                      <Table.Td>{a.requested_by || '—'}</Table.Td>
                      <Table.Td><Text size="xs" c="dimmed">{a.run_id?.slice(0, 8)}</Text></Table.Td>
                      <Table.Td><Text size="sm">{a.expires_at ? new Date(a.expires_at).toLocaleString() : '—'}</Text></Table.Td>
                      <Table.Td>
                        <Group gap="xs">
                          <Button size="xs" color="green" onClick={() => handleApprove(a.approval_id)} loading={approveMut.isPending}>Approve</Button>
                          <Button size="xs" color="red" variant="light" onClick={() => setRejectModal(a.approval_id)}>Reject</Button>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </>
          )}

          {resolved.length > 0 && (
            <>
              <Title order={4}>Resolved ({resolved.length})</Title>
              <Table striped>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Gate</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Decided By</Table.Th>
                    <Table.Th>Reason</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {resolved.map((a) => (
                    <Table.Tr key={a.approval_id}>
                      <Table.Td><Badge variant="light">{a.gate_type}</Badge></Table.Td>
                      <Table.Td><Badge color={statusColor[a.status] ?? 'gray'}>{a.status}</Badge></Table.Td>
                      <Table.Td>{a.decided_by || '—'}</Table.Td>
                      <Table.Td>{a.reason || '—'}</Table.Td>
                    </Table.Tr>
                  ))}
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
