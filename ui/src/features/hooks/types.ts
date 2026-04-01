export type HookType = 'pre' | 'post' | 'scheduled';
export type HookActionType = 'trigger_workflow' | 'webhook';

export interface Hook {
  hook_id: string;
  project_id: string;
  name: string;
  event_pattern: string;
  hook_type: HookType;
  action_type: HookActionType;
  workflow_id: string;
  webhook_url: string;
  conditions: Record<string, unknown> | null;
  params_template: Record<string, string> | null;
  enabled: boolean;
  max_chain_depth: number;
}
