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
} from '@tabler/icons-react';

const navActions = [
  { id: 'dashboard', label: 'Dashboard', description: 'Go to dashboard', path: '/', icon: IconDashboard },
  { id: 'threads', label: 'Threads', description: 'View all threads', path: '/threads', icon: IconMessages },
  { id: 'workflows', label: 'Workflows', description: 'Manage workflow definitions', path: '/workflows', icon: IconGitBranch },
  { id: 'repositories', label: 'Repositories', description: 'Manage repositories', path: '/repositories', icon: IconFolder },
  { id: 'agents', label: 'Agents', description: 'AI agent roles and policies', path: '/agents', icon: IconRobot },
  { id: 'skills', label: 'Skills', description: 'Manage agent skills', path: '/skills', icon: IconCode },
  { id: 'sandboxes', label: 'Sandboxes', description: 'Sandbox environments', path: '/sandboxes', icon: IconBox },
  { id: 'events', label: 'Events', description: 'Explore event store', path: '/events', icon: IconTimeline },
  { id: 'security', label: 'Security', description: 'PII and vault', path: '/security', icon: IconShield },
  { id: 'projects', label: 'Projects', description: 'Manage projects', path: '/projects', icon: IconBriefcase },
  { id: 'pipelines', label: 'Pipelines', description: 'Pipeline runs', path: '/pipelines', icon: IconPlayerPlay },
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
