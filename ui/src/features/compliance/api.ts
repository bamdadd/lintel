/**
 * Manual API hooks for compliance & governance entities.
 * Uses the same customInstance pattern as orval-generated hooks.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';

const BASE = '/api/v1';

// ---------------------------------------------------------------------------
// Generic CRUD hook factory
// ---------------------------------------------------------------------------

interface CrudHooksOptions {
  entityName: string;
  basePath: string;
  idField: string;
}

function createCrudHooks<TCreate, TUpdate>({ entityName, basePath, idField }: CrudHooksOptions) {
  const queryKey = [basePath];

  const useList = (projectId?: string) =>
    useQuery({
      queryKey: projectId ? [...queryKey, { projectId }] : queryKey,
      queryFn: () => {
        const url = projectId ? `${BASE}${basePath}?project_id=${projectId}` : `${BASE}${basePath}`;
        return customInstance<{ data: Record<string, unknown>[] }>(url);
      },
    });

  const useGet = (id: string) =>
    useQuery({
      queryKey: [...queryKey, id],
      queryFn: () => customInstance<{ data: Record<string, unknown> }>(`${BASE}${basePath}/${id}`),
      enabled: !!id,
    });

  const useCreate = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (data: TCreate) =>
        customInstance<{ data: Record<string, unknown> }>(`${BASE}${basePath}`, {
          method: 'POST',
          body: JSON.stringify(data),
        }),
      onSuccess: () => void qc.invalidateQueries({ queryKey }),
    });
  };

  const useUpdate = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: ({ id, data }: { id: string; data: TUpdate }) =>
        customInstance<{ data: Record<string, unknown> }>(`${BASE}${basePath}/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(data),
        }),
      onSuccess: () => void qc.invalidateQueries({ queryKey }),
    });
  };

  const useRemove = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (id: string) =>
        customInstance<void>(`${BASE}${basePath}/${id}`, { method: 'DELETE' }),
      onSuccess: () => void qc.invalidateQueries({ queryKey }),
    });
  };

  return { useList, useGet, useCreate, useUpdate, useRemove, queryKey };
}

// ---------------------------------------------------------------------------
// Entity hooks
// ---------------------------------------------------------------------------

export const regulationHooks = createCrudHooks({
  entityName: 'regulation',
  basePath: '/regulations',
  idField: 'regulation_id',
});

export const compliancePolicyHooks = createCrudHooks({
  entityName: 'compliance-policy',
  basePath: '/compliance-policies',
  idField: 'policy_id',
});

export const procedureHooks = createCrudHooks({
  entityName: 'procedure',
  basePath: '/procedures',
  idField: 'procedure_id',
});

export const practiceHooks = createCrudHooks({
  entityName: 'practice',
  basePath: '/practices',
  idField: 'practice_id',
});

export const strategyHooks = createCrudHooks({
  entityName: 'strategy',
  basePath: '/strategies',
  idField: 'strategy_id',
});

export const kpiHooks = createCrudHooks({
  entityName: 'kpi',
  basePath: '/kpis',
  idField: 'kpi_id',
});

export const experimentHooks = createCrudHooks({
  entityName: 'experiment',
  basePath: '/experiments',
  idField: 'experiment_id',
});

export const complianceMetricHooks = createCrudHooks({
  entityName: 'compliance-metric',
  basePath: '/compliance-metrics',
  idField: 'metric_id',
});

export const knowledgeEntryHooks = createCrudHooks({
  entityName: 'knowledge-entry',
  basePath: '/knowledge-entries',
  idField: 'entry_id',
});

export const knowledgeExtractionHooks = createCrudHooks({
  entityName: 'knowledge-extraction',
  basePath: '/knowledge-extractions',
  idField: 'run_id',
});

// Overview
export const useComplianceOverview = (projectId: string) =>
  useQuery({
    queryKey: ['/compliance/overview', projectId],
    queryFn: () =>
      customInstance<{ data: Record<string, unknown> }>(`${BASE}/compliance/overview/${projectId}`),
    enabled: !!projectId,
  });

// Compliance Config
export const useComplianceConfig = (projectId: string) =>
  useQuery({
    queryKey: ['/compliance/config', projectId],
    queryFn: () =>
      customInstance<{ data: Record<string, unknown> }>(`${BASE}/compliance/config/${projectId}`),
    enabled: !!projectId,
  });

export const useUpdateComplianceConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: string; data: Record<string, unknown> }) =>
      customInstance<{ data: Record<string, unknown> }>(`${BASE}/compliance/config/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    onSuccess: (_d, vars) => {
      void qc.invalidateQueries({ queryKey: ['/compliance/config', vars.projectId] });
    },
  });
};

// Regulation templates
export const useRegulationTemplates = () =>
  useQuery({
    queryKey: ['/compliance/regulation-templates'],
    queryFn: () =>
      customInstance<{ data: Record<string, unknown>[] }>(`${BASE}/compliance/regulation-templates`),
  });

export const useAddRegulationFromTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { template_id: string; project_id: string }) =>
      customInstance<{ data: Record<string, unknown> }>(`${BASE}/compliance/regulation-from-template`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['/regulations'] });
      void qc.invalidateQueries({ queryKey: ['/compliance/overview'] });
    },
  });
};
