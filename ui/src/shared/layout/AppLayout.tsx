import {
  AppShell,
  Burger,
  Group,
  NavLink,
  Title,
  ActionIcon,
  useMantineColorScheme,
  ScrollArea,
  Divider,
  Text,
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
  IconBell,
  IconHistory,
  IconBolt,
  IconVariable,
  IconServer,
  IconLock,
  IconBrain,
  IconCpu,
  IconPackage,
  IconCheckbox,
  IconListCheck,
  IconPlug,
} from '@tabler/icons-react';
import type { Icon } from '@tabler/icons-react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { CommandPalette } from '@/shared/components/CommandPalette';
import { ConnectionStatus } from '@/shared/components/ConnectionStatus';

interface NavSection {
  label: string;
  items: { label: string; path: string; icon: Icon }[];
}

const navSections: NavSection[] = [
  {
    label: 'Core',
    items: [
      { label: 'Dashboard', path: '/', icon: IconDashboard },
      { label: 'Chat', path: '/chat', icon: IconMessageCircle },
      { label: 'Threads', path: '/threads', icon: IconMessages },
      { label: 'Work Items', path: '/work-items', icon: IconListCheck },
    ],
  },
  {
    label: 'Development',
    items: [
      { label: 'Workflows', path: '/workflows', icon: IconGitBranch },
      { label: 'Pipelines', path: '/pipelines', icon: IconPlayerPlay },
      { label: 'Repositories', path: '/repositories', icon: IconFolder },
      { label: 'Sandboxes', path: '/sandboxes', icon: IconBox },
      { label: 'Artifacts', path: '/artifacts', icon: IconPackage },
    ],
  },
  {
    label: 'AI & Agents',
    items: [
      { label: 'Agents', path: '/agents', icon: IconRobot },
      { label: 'Skills', path: '/skills', icon: IconCode },
      { label: 'AI Providers', path: '/ai-providers', icon: IconBrain },
      { label: 'Models', path: '/models', icon: IconCpu },
      { label: 'MCP Servers', path: '/mcp-servers', icon: IconPlug },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { label: 'Projects', path: '/projects', icon: IconBriefcase },
      { label: 'Environments', path: '/environments', icon: IconServer },
      { label: 'Variables', path: '/variables', icon: IconVariable },
      { label: 'Triggers', path: '/triggers', icon: IconBolt },
      { label: 'Policies', path: '/policies', icon: IconLock },
      { label: 'Notifications', path: '/notifications', icon: IconBell },
    ],
  },
  {
    label: 'Administration',
    items: [
      { label: 'Users', path: '/users', icon: IconUsers },
      { label: 'Teams', path: '/teams', icon: IconUsersGroup },
      { label: 'Approvals', path: '/approvals', icon: IconCheckbox },
      { label: 'Security', path: '/security', icon: IconShield },
      { label: 'Events', path: '/events', icon: IconTimeline },
      { label: 'Audit', path: '/audit', icon: IconHistory },
      { label: 'Settings', path: '/settings', icon: IconSettings },
    ],
  },
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
      <AppShell.Navbar p="xs">
        <ScrollArea>
          {navSections.map((section, i) => (
            <div key={section.label}>
              {i > 0 && <Divider my={4} />}
              <Text size="xs" fw={700} c="dimmed" px="sm" py={4} tt="uppercase">
                {section.label}
              </Text>
              {section.items.map((item) => (
                <NavLink
                  key={item.path}
                  label={item.label}
                  leftSection={<item.icon size={18} stroke={1.5} />}
                  active={location.pathname === item.path}
                  onClick={() => void navigate(item.path)}
                  py={4}
                  style={{ borderRadius: 4 }}
                />
              ))}
            </div>
          ))}
        </ScrollArea>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
      <CommandPalette />
    </AppShell>
  );
}
