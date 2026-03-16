export interface FlowStep {
  file_path: string;
  function_name: string;
  line_number: number;
  step_type: string;
  description: string;
}

export interface FlowEntry {
  flow_id: string;
  flow_map_id: string;
  flow_type: string;
  name: string;
  source: FlowStep;
  steps: FlowStep[];
  sink: FlowStep | null;
  metadata: Record<string, unknown>;
}

export interface FlowDiagram {
  diagram_id: string;
  flow_map_id: string;
  flow_type: string;
  title: string;
  mermaid_source: string;
  flow_ids: string[];
}

export interface FlowMetrics {
  metrics_id: string;
  flow_map_id: string;
  total_flows: number;
  flows_by_type: Record<string, number>;
  avg_depth: number;
  max_depth: number;
  complexity_score: number;
}

export interface ProcessFlowMap {
  flow_map_id: string;
  repository_id: string;
  workflow_run_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const FLOW_TYPE_COLORS: Record<string, string> = {
  http_request: '#228be6',
  event_sourcing: '#40c057',
  command_dispatch: '#7950f2',
  background_job: '#fd7e14',
  external_integration: '#fa5252',
};

export const FLOW_TYPE_LABELS: Record<string, string> = {
  http_request: 'HTTP Request',
  event_sourcing: 'Event Sourcing',
  command_dispatch: 'Command Dispatch',
  background_job: 'Background Job',
  external_integration: 'External Integration',
};
