import { type PipelineStageCardProps, type StageStatus } from './types';
import {
  IconCircleCheck, IconCircleX, IconLoader2, IconClock,
  IconCircleDashed, IconPlayerPause, IconShieldCheck, IconPencil,
  IconRefresh,
} from '@tabler/icons-react';
import styles from './PipelineStageCard.module.css';

const STATUS_CONFIG: Record<string, {
  icon: React.ElementType;
  color: string;
  bg: string;
  border: string;
  glow?: string;
}> = {
  succeeded: { icon: IconCircleCheck, color: '#22c55e', bg: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.3)' },
  approved: { icon: IconShieldCheck, color: '#14b8a6', bg: 'rgba(20,184,166,0.08)', border: 'rgba(20,184,166,0.3)' },
  failed: { icon: IconCircleX, color: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.3)' },
  rejected: { icon: IconCircleX, color: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.3)' },
  running: { icon: IconLoader2, color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.5)', glow: '0 0 12px rgba(59,130,246,0.3)' },
  waiting_approval: { icon: IconPlayerPause, color: '#eab308', bg: 'rgba(234,179,8,0.08)', border: 'rgba(234,179,8,0.4)', glow: '0 0 10px rgba(234,179,8,0.2)' },
  pending: { icon: IconClock, color: '#6b7280', bg: 'rgba(107,114,128,0.05)', border: 'rgba(107,114,128,0.2)' },
  skipped: { icon: IconCircleDashed, color: '#6b7280', bg: 'rgba(107,114,128,0.05)', border: 'rgba(107,114,128,0.2)' },
  cancelled: { icon: IconCircleX, color: '#f97316', bg: 'rgba(249,115,22,0.08)', border: 'rgba(249,115,22,0.3)' },
  timed_out: { icon: IconClock, color: '#f97316', bg: 'rgba(249,115,22,0.08)', border: 'rgba(249,115,22,0.3)' },
  report_ready: { icon: IconPencil, color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.4)', glow: '0 0 10px rgba(245,158,11,0.2)' },
  regenerating: { icon: IconRefresh, color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.5)', glow: '0 0 12px rgba(59,130,246,0.3)' },
};

const DEFAULT_STATUS = STATUS_CONFIG.pending!;

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
}

export function PipelineStageCard(props: PipelineStageCardProps) {
  const { variant, data, selected, onClick } = props;
  const cfg = STATUS_CONFIG[data.status] ?? DEFAULT_STATUS;
  const Icon = cfg.icon;
  const isRunning = data.status === 'running' || data.status === 'regenerating';
  const isApprovalGate = variant === 'stage' && data.stageType?.includes('approv');

  return (
    <div
      className={styles.card}
      data-selected={selected || undefined}
      onClick={onClick}
      style={{
        borderRadius: isApprovalGate ? 24 : 10,
        background: cfg.bg,
        border: `1.5px solid ${selected ? cfg.color : cfg.border}`,
        boxShadow: selected ? `0 0 0 2px ${cfg.color}40` : cfg.glow ?? 'none',
      }}
    >
      <div className={styles.header}>
        <Icon
          size={18}
          color={cfg.color}
          stroke={1.8}
          className={isRunning ? styles.spinning : undefined}
        />
        <span className={styles.name}>{data.name}</span>
      </div>
      <div className={styles.footer}>
        {data.durationMs != null && data.durationMs > 0 && (
          <span className={styles.duration} style={{ color: cfg.color }}>
            {formatDuration(data.durationMs)}
          </span>
        )}
        {variant === 'stage' && data.artifactCount != null && data.artifactCount > 0 && (
          <span className={styles.badge}>
            {data.artifactCount} artifact{data.artifactCount > 1 ? 's' : ''}
          </span>
        )}
        {variant === 'agent-group' && data.agentCount != null && data.agentCount > 0 && (
          <span className={styles.badge}>
            {data.agentCount} agent{data.agentCount > 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
}
