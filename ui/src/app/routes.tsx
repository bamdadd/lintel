import { createBrowserRouter } from 'react-router';
import { AppLayout } from '@/shared/layout/AppLayout';
import { RouteError } from '@/shared/components/RouteError';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      {
        index: true,
        lazy: () => import('@/features/dashboard/pages/DashboardPage'),
      },
      {
        path: 'threads',
        lazy: () => import('@/features/threads/pages/ThreadListPage'),
      },
      {
        path: 'threads/:streamId',
        lazy: () => import('@/features/threads/pages/ThreadDetailPage'),
      },
      {
        path: 'workflows',
        lazy: () => import('@/features/workflows/pages/WorkflowListPage'),
      },
      {
        path: 'workflows/editor/:id?',
        lazy: () => import('@/features/workflows/pages/WorkflowEditorPage'),
      },
      {
        path: 'repositories',
        lazy: () => import('@/features/repositories/pages/RepositoryListPage'),
      },
      {
        path: 'repositories/:repoId',
        lazy: () =>
          import('@/features/repositories/pages/RepositoryDetailPage'),
      },
      {
        path: 'agents',
        lazy: () => import('@/features/agents/pages/AgentListPage'),
      },
      {
        path: 'agents/:role',
        lazy: () => import('@/features/agents/pages/AgentDetailPage'),
      },
      {
        path: 'skills',
        lazy: () => import('@/features/skills/pages/SkillListPage'),
      },
      {
        path: 'sandboxes',
        lazy: () => import('@/features/sandboxes/pages/SandboxListPage'),
      },
      {
        path: 'events',
        lazy: () => import('@/features/events/pages/EventExplorerPage'),
      },
      {
        path: 'security',
        lazy: () => import('@/features/security/pages/SecurityDashboardPage'),
      },
      {
        path: 'projects',
        lazy: () => import('@/features/projects/pages/ProjectListPage'),
      },
      {
        path: 'projects/:projectId',
        lazy: () => import('@/features/projects/pages/ProjectDetailPage'),
      },
      {
        path: 'pipelines',
        lazy: () => import('@/features/pipelines/pages/PipelineListPage'),
      },
      {
        path: 'settings',
        lazy: () => import('@/features/settings/pages/SettingsPage'),
      },
    ],
  },
  {
    path: '/setup',
    lazy: () => import('@/features/settings/pages/SetupWizardPage'),
  },
]);
