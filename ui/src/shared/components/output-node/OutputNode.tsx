import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  IconGitPullRequest, IconChecks, IconLink,
} from '@tabler/icons-react';
import styles from './OutputNode.module.css';

const OUTPUT_ICONS: Record<string, React.ElementType> = {
  pr_url: IconGitPullRequest,
  verdict: IconChecks,
};

export interface OutputNodeData {
  label: string;
  outputKind: string;
  [key: string]: unknown;
}

export function OutputNode({ data }: NodeProps & { data: OutputNodeData }) {
  const Icon = OUTPUT_ICONS[data.outputKind] ?? IconLink;
  return (
    <div className={styles.output}>
      <Handle
        type="target"
        position={Position.Left}
        className={styles.handle}
      />
      <Icon size={16} color="#14b8a6" stroke={1.8} />
      <span className={styles.label}>{data.label}</span>
    </div>
  );
}
