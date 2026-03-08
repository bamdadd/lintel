import { Spotlight, spotlight } from '@mantine/spotlight';
import { useNavigate } from 'react-router';
import {
  IconDashboard,
  IconMessages,
  IconGitBranch,
  IconFolder,
  IconRobot,
  IconCode,
  IconBox,
  IconTimeline,
  IconShield,
  IconBriefcase,
  IconPlayerPlay,
  IconSettings,
  IconMessageCircle,
  IconUsers,
  IconUsersGroup,
  IconBell,
  IconHistory,
  IconBolt,
  IconVariable,
  IconServer,
  IconLock,
  IconBrain,
  IconPackage,
  IconCheckbox,
  IconListCheck,
  IconLayoutKanban,
} from '@tabler/icons-react';

const navActions = [
  { id: 'dashboard', label: 'Dashboard', description: 'Go to dashboard', path: '/', icon: IconDashboard },
  { id: 'chat', label: 'Chat', description: 'Chat with agents', path: '/chat', icon: IconMessageCircle },
  { id: 'threads', label: 'Threads', description: 'View all threads', path: '/threads', icon: IconMessages },
  { id: 'work-items', label: 'Work Items', description: 'Track features and bugs', path: '/work-items', icon: IconListCheck },
  { id: 'boards', label: 'Boards', description: 'Kanban boards for work items', path: '/boards', icon: IconLayoutKanban },
  { id: 'workflows', label: 'Workflows', description: 'Manage workflow definitions', path: '/workflows', icon: IconGitBranch },
  { id: 'pipelines', label: 'Pipelines', description: 'Pipeline runs', path: '/pipelines', icon: IconPlayerPlay },
  { id: 'repositories', label: 'Repositories', description: 'Manage repositories', path: '/repositories', icon: IconFolder },
  { id: 'sandboxes', label: 'Sandboxes', description: 'Sandbox environments', path: '/sandboxes', icon: IconBox },
  { id: 'artifacts', label: 'Artifacts', description: 'Code artifacts and test results', path: '/artifacts', icon: IconPackage },
  { id: 'agents', label: 'Agents', description: 'AI agent roles and policies', path: '/agents', icon: IconRobot },
  { id: 'skills', label: 'Skills', description: 'Manage agent skills', path: '/skills', icon: IconCode },
  { id: 'ai-providers', label: 'AI Providers', description: 'Configure LLM providers', path: '/ai-providers', icon: IconBrain },
  { id: 'projects', label: 'Projects', description: 'Manage projects', path: '/projects', icon: IconBriefcase },
  { id: 'environments', label: 'Environments', description: 'Manage environments', path: '/environments', icon: IconServer },
  { id: 'variables', label: 'Variables', description: 'Configuration variables', path: '/variables', icon: IconVariable },
  { id: 'credentials', label: 'Credentials', description: 'SSH keys, tokens, API keys', path: '/credentials', icon: IconLock },
  { id: 'triggers', label: 'Triggers', description: 'Automation triggers', path: '/triggers', icon: IconBolt },
  { id: 'policies', label: 'Policies', description: 'Approval and security policies', path: '/policies', icon: IconLock },
  { id: 'notifications', label: 'Notifications', description: 'Notification rules', path: '/notifications', icon: IconBell },
  { id: 'users', label: 'Users', description: 'Manage users', path: '/users', icon: IconUsers },
  { id: 'teams', label: 'Teams', description: 'Manage teams', path: '/teams', icon: IconUsersGroup },
  { id: 'approvals', label: 'Approvals', description: 'Approval requests', path: '/approvals', icon: IconCheckbox },
  { id: 'security', label: 'Security', description: 'PII and vault', path: '/security', icon: IconShield },
  { id: 'events', label: 'Events', description: 'Explore event store', path: '/events', icon: IconTimeline },
  { id: 'audit', label: 'Audit', description: 'Audit log', path: '/audit', icon: IconHistory },
  { id: 'settings', label: 'Settings', description: 'Platform settings', path: '/settings', icon: IconSettings },
];

export function CommandPalette() {
  const navigate = useNavigate();

  return (
    <Spotlight
      actions={navActions.map((a) => ({
        id: a.id,
        label: a.label,
        description: a.description,
        onClick: () => void navigate(a.path),
        leftSection: <a.icon size={20} />,
      }))}
      shortcut="mod+K"
      nothingFound="No matching actions"
    />
  );
}

export { spotlight };
