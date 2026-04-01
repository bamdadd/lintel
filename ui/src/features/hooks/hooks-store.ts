/**
 * In-memory hooks store — no backend API exists yet.
 * Replace with generated API hooks when the REST API is created.
 */
import { useState, useCallback } from 'react';
import type { Hook } from './types';

const SEED_HOOKS: Hook[] = [
  {
    hook_id: 'hook-1',
    project_id: 'proj-1',
    name: 'Auto-review on PR',
    event_pattern: 'PullRequest*',
    hook_type: 'post',
    action_type: 'trigger_workflow',
    workflow_id: 'wf-review',
    webhook_url: '',
    conditions: null,
    params_template: { repo: '{{ event.repo }}' },
    enabled: true,
    max_chain_depth: 5,
  },
  {
    hook_id: 'hook-2',
    project_id: 'proj-1',
    name: 'Block deploys without approval',
    event_pattern: 'PipelineRunStarted',
    hook_type: 'pre',
    action_type: 'trigger_workflow',
    workflow_id: '',
    webhook_url: '',
    conditions: { stage: 'deploy' },
    params_template: null,
    enabled: true,
    max_chain_depth: 3,
  },
  {
    hook_id: 'hook-3',
    project_id: 'proj-2',
    name: 'Notify on completion',
    event_pattern: '*Completed',
    hook_type: 'post',
    action_type: 'webhook',
    workflow_id: '',
    webhook_url: 'https://hooks.example.com/notify',
    conditions: null,
    params_template: null,
    enabled: false,
    max_chain_depth: 5,
  },
];

let nextId = 4;

export function useHooksStore() {
  const [hooks, setHooks] = useState<Hook[]>(SEED_HOOKS);

  const createHook = useCallback((data: Omit<Hook, 'hook_id'>) => {
    const hook: Hook = { ...data, hook_id: `hook-${nextId++}` };
    setHooks((prev) => [...prev, hook]);
    return hook;
  }, []);

  const updateHook = useCallback((hookId: string, data: Partial<Hook>) => {
    setHooks((prev) =>
      prev.map((h) => (h.hook_id === hookId ? { ...h, ...data } : h)),
    );
  }, []);

  const deleteHook = useCallback((hookId: string) => {
    setHooks((prev) => prev.filter((h) => h.hook_id !== hookId));
  }, []);

  const getHook = useCallback(
    (hookId: string) => hooks.find((h) => h.hook_id === hookId) ?? null,
    [hooks],
  );

  return { hooks, createHook, updateHook, deleteHook, getHook };
}
