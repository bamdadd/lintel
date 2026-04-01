import { Handle, Position, type NodeProps } from '@xyflow/react';
import { PipelineStageCard } from '../components/pipeline-stage-card';
import { TriggerNode } from '../components/trigger-node';
import { ArtifactNode } from '../components/artifact-node';
import { OutputNode } from '../components/output-node';
import type { PipelineStageData } from '../components/pipeline-stage-card/types';

interface StageNodeData extends PipelineStageData {
  [key: string]: unknown;
}

function StageNode({ data, selected }: NodeProps & { data: StageNodeData }) {
  return (
    <div>
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: 'rgba(107,114,128,0.3)', border: 'none', width: 6, height: 6 }}
      />
      <PipelineStageCard
        variant="stage"
        data={data}
        selected={selected}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: 'rgba(107,114,128,0.3)', border: 'none', width: 6, height: 6 }}
      />
    </div>
  );
}

export const NODE_RENDERERS = {
  stage: StageNode,
  trigger: TriggerNode,
  artifact: ArtifactNode,
  output: OutputNode,
} as const;

export type { NodeType, NodeDescriptor, AnyNodeDescriptor } from './types';
