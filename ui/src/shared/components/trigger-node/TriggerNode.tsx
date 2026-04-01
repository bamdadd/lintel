import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  IconMessageCircle, IconGitBranch, IconWebhook, IconClockHour4,
  IconUser, IconBolt, IconBriefcase,
} from '@tabler/icons-react';
import type { TriggerNodeData } from './types';
import styles from './TriggerNode.module.css';

const TRIGGER_ICONS: Record<string, React.ElementType> = {
  chat: IconMessageCircle,
  slack_message: IconMessageCircle,
  git: IconGitBranch,
  pr_event: IconGitBranch,
  webhook: IconWebhook,
  schedule: IconClockHour4,
  manual: IconUser,
  work_item: IconBriefcase,
};

export function TriggerNode({ data }: NodeProps & { data: TriggerNodeData }) {
  const Icon = TRIGGER_ICONS[data.triggerKind] ?? IconBolt;
  return (
    <div className={styles.trigger}>
      <Icon size={16} color="#eab308" stroke={1.8} />
      <span className={styles.label}>{data.label}</span>
      {data.timestamp && (
        <span className={styles.timestamp}>{data.timestamp}</span>
      )}
      <Handle
        type="source"
        position={Position.Right}
        className={styles.handle}
      />
    </div>
  );
}
