export type TriggerKind =
  | 'chat'
  | 'slack_message'
  | 'webhook'
  | 'schedule'
  | 'pr_event'
  | 'manual'
  | 'work_item'
  | 'git';

export interface TriggerNodeData {
  label: string;
  triggerKind: TriggerKind;
  timestamp?: string;
  [key: string]: unknown;
}
