import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

interface ApprovalGateData {
  label: string;
}

export function ApprovalGateNode({ data, selected }: NodeProps & { data: ApprovalGateData }) {
  return (
    <div
      style={{
        padding: 12,
        borderRadius: 8,
        background: 'var(--mantine-color-body)',
        border: `2px solid ${selected ? 'var(--mantine-color-yellow-6)' : 'var(--mantine-color-default-border)'}`,
        minWidth: 150,
        textAlign: 'center',
      }}
    >
      <Handle type="target" position={Position.Top} />
      <strong>{data.label}</strong>
      <div style={{ fontSize: 11, opacity: 0.6 }}>Approval Gate</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
