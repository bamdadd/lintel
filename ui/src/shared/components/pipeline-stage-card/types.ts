export type StageStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped'
  | 'waiting_approval'
  | 'approved'
  | 'rejected'
  | 'timed_out'
  | 'cancelled'
  | 'report_ready'
  | 'regenerating';

export interface PipelineStageData {
  name: string;
  status: StageStatus;
  durationMs?: number;
  artifactCount?: number;
  stageType?: string;
}

export interface AgentGroupData {
  name: string;
  status: StageStatus;
  agentCount?: number;
  durationMs?: number;
}

export type PipelineStageCardProps =
  | { variant: 'stage'; data: PipelineStageData; selected?: boolean; onClick?: () => void }
  | { variant: 'agent-group'; data: AgentGroupData; selected?: boolean; onClick?: () => void };
