import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

interface AgentStepData {
  label: string;
  role: string;
}

export function AgentStepNode({ data, selected }: NodeProps & { data: AgentStepData }) {
  return (
    <div
      style={{
        padding: 12,
        borderRadius: 8,
        background: 'var(--mantine-color-body)',
        border: `2px solid ${selected ? 'var(--mantine-color-indigo-6)' : 'var(--mantine-color-default-border)'}`,
        minWidth: 150,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <strong>{data.label}</strong>
      <div style={{ fontSize: 12, opacity: 0.7 }}>{data.role}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
