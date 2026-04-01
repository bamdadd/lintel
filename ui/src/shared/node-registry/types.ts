import type { PipelineStageData, AgentGroupData } from '../components/pipeline-stage-card/types';
import type { TriggerNodeData } from '../components/trigger-node/types';
import type { OutputNodeData } from '../components/output-node/OutputNode';
import type { ArtifactNodeData } from '../components/artifact-node/types';

export type NodeType = 'stage' | 'trigger' | 'artifact' | 'output';

export interface NodeDescriptor<T = unknown> {
  id: string;
  type: NodeType;
  label: string;
  metadata: T;
}

export type StageNodeDescriptor = NodeDescriptor<PipelineStageData>;
export type TriggerNodeDescriptor = NodeDescriptor<TriggerNodeData>;
export type ArtifactNodeDescriptor = NodeDescriptor<ArtifactNodeData>;
export type OutputNodeDescriptor = NodeDescriptor<OutputNodeData>;

export type AnyNodeDescriptor =
  | StageNodeDescriptor
  | TriggerNodeDescriptor
  | ArtifactNodeDescriptor
  | OutputNodeDescriptor;
