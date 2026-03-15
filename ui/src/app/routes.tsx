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
        path: 'sandboxes/:sandboxId',
        lazy: () => import('@/features/sandboxes/pages/SandboxDetailPage'),
      },
      {
        path: 'events',
        lazy: () => import('@/features/events/pages/EventExplorerPage'),
      },
      {
        path: 'pii-stats',
        lazy: () => import('@/features/pii/pages/PiiStatsPage'),
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
        path: 'chat/:conversationId',
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
        path: 'automations',
        lazy: () => import('@/features/automations/pages/AutomationListPage'),
      },
      {
        path: 'automations/:automationId',
        lazy: () => import('@/features/automations/pages/AutomationDetailPage'),
      },
      {
        path: 'triggers',
        lazy: () => import('@/features/triggers/pages/TriggerListPage'),
      },
      {
        path: 'credentials',
        lazy: () => import('@/features/credentials/pages/CredentialListPage'),
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
        path: 'test-results',
        lazy: () => import('@/features/testing/pages/TestResultsPage'),
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
        path: 'boards',
        lazy: () => import('@/features/boards/pages/BoardListPage'),
      },
      {
        path: 'boards/tags',
        lazy: () => import('@/features/boards/pages/TagManagementPage'),
      },
      {
        path: 'boards/:boardId',
        lazy: () => import('@/features/boards/pages/BoardPage'),
      },
      // --- Compliance & Governance ---
      {
        path: 'compliance',
        lazy: () => import('@/features/compliance/pages/ComplianceDashboardPage'),
      },
      {
        path: 'compliance/regulations',
        lazy: () => import('@/features/compliance/pages/RegulationListPage'),
      },
      {
        path: 'compliance/policies',
        lazy: () => import('@/features/compliance/pages/CompliancePolicyListPage'),
      },
      {
        path: 'compliance/procedures',
        lazy: () => import('@/features/compliance/pages/ProcedureListPage'),
      },
      {
        path: 'compliance/practices',
        lazy: () => import('@/features/compliance/pages/PracticeListPage'),
      },
      {
        path: 'compliance/architecture-decisions',
        lazy: () => import('@/features/compliance/pages/ArchitectureDecisionListPage'),
      },
      // --- Experimentation ---
      {
        path: 'experimentation/strategies',
        lazy: () => import('@/features/experimentation/pages/StrategyListPage'),
      },
      {
        path: 'experimentation/kpis',
        lazy: () => import('@/features/experimentation/pages/KPIListPage'),
      },
      {
        path: 'experimentation/experiments',
        lazy: () => import('@/features/experimentation/pages/ExperimentListPage'),
      },
      {
        path: 'experimentation/metrics',
        lazy: () => import('@/features/experimentation/pages/ComplianceMetricListPage'),
      },
      // --- Knowledge Base ---
      {
        path: 'knowledge',
        lazy: () => import('@/features/knowledge/pages/KnowledgeBasePage'),
      },
      {
        path: 'debug',
        lazy: () => import('@/features/debug/pages/DebugPage'),
      },
      {
        path: 'settings',
        lazy: () => import('@/features/settings/pages/SettingsPage'),
      },
      {
        path: 'settings/channels',
        lazy: () => import('@/features/channels/ChannelsPage'),
      },
    ],
  },
  {
    path: '/setup',
    lazy: () => import('@/features/settings/pages/SetupWizardPage'),
  },
]);
