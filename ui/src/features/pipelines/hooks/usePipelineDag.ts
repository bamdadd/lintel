import { useMemo } from 'react';
import type { Node, Edge } from '@xyflow/react';
import { usePipelinesGetPipeline, usePipelinesListStages } from '@/generated/api/pipelines/pipelines';
import { useWorkflowDefinitionsGetWorkflowDefinition } from '@/generated/api/workflow-definitions/workflow-definitions';
import {
  buildDagNodes,
  type PipelineRunData,
  type StageData,
  type WorkflowDefinitionData,
} from './transformers';

interface UsePipelineDagResult {
  nodes: Node[];
  edges: Edge[];
  pipeline: PipelineRunData | null;
  stages: StageData[];
  isLoading: boolean;
  error: Error | null;
}

export function usePipelineDag(pipelineRunId: string | null): UsePipelineDagResult {
  const enabled = !!pipelineRunId;

  const {
    data: pipelineResp,
    isLoading: pipelineLoading,
    error: pipelineError,
  } = usePipelinesGetPipeline(pipelineRunId ?? '', {
    query: { enabled, staleTime: 0 },
  });

  const {
    data: stagesResp,
    isLoading: stagesLoading,
    error: stagesError,
  } = usePipelinesListStages(pipelineRunId ?? '', {
    query: { enabled, staleTime: 0 },
  });

  const pipeline = (pipelineResp?.data ?? null) as PipelineRunData | null;
  const stages = (stagesResp?.data ?? []) as StageData[];

  const workflowDefId = pipeline?.workflow_definition_id;
  const {
    data: workflowResp,
    isLoading: workflowLoading,
    error: workflowError,
  } = useWorkflowDefinitionsGetWorkflowDefinition(workflowDefId ?? '', {
    query: { enabled: !!workflowDefId, staleTime: 30_000 },
  });

  const workflowDef = (workflowResp?.data ?? null) as WorkflowDefinitionData | null;

  const isLoading = pipelineLoading || stagesLoading || workflowLoading;
  const error = (pipelineError ?? stagesError ?? workflowError) as Error | null;

  const { nodes, edges } = useMemo(() => {
    if (!pipeline || stages.length === 0) {
      return { nodes: [], edges: [] };
    }
    return buildDagNodes(pipeline, stages, workflowDef ?? undefined);
  }, [pipeline, stages, workflowDef]);

  return { nodes, edges, pipeline, stages, isLoading, error };
}
