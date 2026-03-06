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
import { IconSun, IconMoon } from '@tabler/icons-react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { CommandPalette } from '@/shared/components/CommandPalette';
import { ConnectionStatus } from '@/shared/components/ConnectionStatus';

const navItems = [
  { label: 'Dashboard', path: '/' },
  { label: 'Threads', path: '/threads' },
  { label: 'Workflows', path: '/workflows' },
  { label: 'Repositories', path: '/repositories' },
  { label: 'Agents', path: '/agents' },
  { label: 'Skills', path: '/skills' },
  { label: 'Sandboxes', path: '/sandboxes' },
  { label: 'Events', path: '/events' },
  { label: 'Security', path: '/security' },
  { label: 'Projects', path: '/projects' },
  { label: 'Pipelines', path: '/pipelines' },
  { label: 'Settings', path: '/settings' },
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
      </AppShell.Header>
      <AppShell.Navbar p="md">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            label={item.label}
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
