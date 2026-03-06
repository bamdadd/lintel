import {
  AppShell,
  Burger,
  Group,
  NavLink,
  Title,
  ActionIcon,
  useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconSun,
  IconMoon,
  IconDashboard,
  IconMessageCircle,
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
  IconUsers,
  IconUsersGroup,
} from '@tabler/icons-react';
import type { Icon } from '@tabler/icons-react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { CommandPalette } from '@/shared/components/CommandPalette';
import { ConnectionStatus } from '@/shared/components/ConnectionStatus';

const navItems: { label: string; path: string; icon: Icon }[] = [
  { label: 'Dashboard', path: '/', icon: IconDashboard },
  { label: 'Chat', path: '/chat', icon: IconMessageCircle },
  { label: 'Threads', path: '/threads', icon: IconMessages },
  { label: 'Workflows', path: '/workflows', icon: IconGitBranch },
  { label: 'Repositories', path: '/repositories', icon: IconFolder },
  { label: 'Agents', path: '/agents', icon: IconRobot },
  { label: 'Skills', path: '/skills', icon: IconCode },
  { label: 'Sandboxes', path: '/sandboxes', icon: IconBox },
  { label: 'Events', path: '/events', icon: IconTimeline },
  { label: 'Security', path: '/security', icon: IconShield },
  { label: 'Projects', path: '/projects', icon: IconBriefcase },
  { label: 'Users', path: '/users', icon: IconUsers },
  { label: 'Teams', path: '/teams', icon: IconUsersGroup },
  { label: 'Pipelines', path: '/pipelines', icon: IconPlayerPlay },
  { label: 'Settings', path: '/settings', icon: IconSettings },
];

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure();
  const navigate = useNavigate();
  const location = useLocation();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: 240,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
            />
            <Title order={3}>Lintel</Title>
          </Group>
          <Group gap="sm">
            <ConnectionStatus />
            <ActionIcon
              variant="default"
              onClick={toggleColorScheme}
              aria-label="Toggle color scheme"
            >
              {colorScheme === 'dark' ? (
                <IconSun size={18} />
              ) : (
                <IconMoon size={18} />
              )}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            label={item.label}
            leftSection={<item.icon size={18} stroke={1.5} />}
            active={location.pathname === item.path}
            onClick={() => void navigate(item.path)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
      <CommandPalette />
    </AppShell>
  );
}
