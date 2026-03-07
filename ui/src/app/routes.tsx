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
        path: 'chat',
        lazy: () => import('@/features/chat/pages/ChatPage'),
      },
      {
        path: 'pipelines',
        lazy: () => import('@/features/pipelines/pages/PipelineListPage'),
      },
      {
        path: 'pipelines/runs/:runId',
        lazy: () => import('@/features/pipelines/pages/RunDetailPage'),
      },
      {
        path: 'pipelines/:runId',
        lazy: () => import('@/features/pipelines/pages/PipelineDetailPage'),
      },
      {
        path: 'pipelines/metrics',
        lazy: () => import('@/features/pipelines/pages/MetricsDashboardPage'),
      },
      {
        path: 'users',
        lazy: () => import('@/features/users/pages/UserListPage'),
      },
      {
        path: 'teams',
        lazy: () => import('@/features/teams/pages/TeamListPage'),
      },
      {
        path: 'notifications',
        lazy: () => import('@/features/notifications/pages/NotificationListPage'),
      },
      {
        path: 'audit',
        lazy: () => import('@/features/audit/pages/AuditLogPage'),
      },
      {
        path: 'triggers',
        lazy: () => import('@/features/triggers/pages/TriggerListPage'),
      },
      {
        path: 'variables',
        lazy: () => import('@/features/variables/pages/VariableListPage'),
      },
      {
        path: 'environments',
        lazy: () => import('@/features/environments/pages/EnvironmentListPage'),
      },
      {
        path: 'policies',
        lazy: () => import('@/features/policies/pages/PolicyListPage'),
      },
      {
        path: 'ai-providers',
        lazy: () => import('@/features/ai-providers/pages/AIProviderListPage'),
      },
      {
        path: 'models',
        lazy: () => import('@/features/models/pages/ModelListPage'),
      },
      {
        path: 'mcp-servers',
        lazy: () => import('@/features/mcp-servers/pages/MCPServerListPage'),
      },
      {
        path: 'artifacts',
        lazy: () => import('@/features/artifacts/pages/ArtifactListPage'),
      },
      {
        path: 'approvals',
        lazy: () => import('@/features/approval-requests/pages/ApprovalRequestListPage'),
      },
      {
        path: 'work-items',
        lazy: () => import('@/features/work-items/pages/WorkItemListPage'),
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
