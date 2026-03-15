export interface IntegrationMap {
  map_id: string;
  repository_id: string;
  workflow_run_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceNode {
  node_id: string;
  integration_map_id: string;
  service_name: string;
  language: string;
  metadata: Record<string, unknown>;
}

export interface IntegrationEdge {
  edge_id: string;
  integration_map_id: string;
  source_node_id: string;
  target_node_id: string;
  integration_type: string;
  protocol: string;
  metadata: Record<string, unknown>;
}

export interface PatternCatalogueEntry {
  entry_id: string;
  integration_map_id: string;
  pattern_type: string;
  pattern_name: string;
  occurrences: number;
  details: Record<string, unknown>;
}

export interface AntipatternDetection {
  detection_id: string;
  integration_map_id: string;
  antipattern_type: string;
  severity: string;
  affected_nodes: string[];
  description: string;
}

export interface ServiceCouplingScore {
  score_id: string;
  integration_map_id: string;
  service_node_id: string;
  afferent_coupling: number;
  efferent_coupling: number;
  instability: number;
  computed_at: string;
}

export interface GraphData {
  nodes: ServiceNode[];
  edges: IntegrationEdge[];
}

// Integration type colors for graph
export const INTEGRATION_TYPE_COLORS: Record<string, string> = {
  sync: '#228be6',      // blue
  async: '#40c057',     // green
  database: '#fd7e14',  // orange
  file: '#868e96',      // grey
  external: '#fa5252',  // red
};
