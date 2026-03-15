import { useState, useEffect } from 'react';
import {
  AppShell,
  Burger,
  Group,
  NavLink,
  Title,
  ActionIcon,
  useMantineColorScheme,
  ScrollArea,
  Text,
  Box,
  Tooltip,
  Kbd,
  UnstyledButton,
  Collapse,
} from '@mantine/core';
import { useDisclosure, useHotkeys, useLocalStorage } from '@mantine/hooks';
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
  IconShieldCheck,
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
  IconLayoutKanban,
  IconFingerprint,
  IconTestPipe2,
  IconFileText,
  IconListDetails,
  IconTool,
  IconTarget,
  IconChartBar,
  IconFlask,
  IconBulb,
  IconBug,
  IconCalendarEvent,
  IconChevronRight,
  IconSearch,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
} from '@tabler/icons-react';
import type { Icon } from '@tabler/icons-react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import { ClaudeCredentialsBanner } from '@/shared/components/ClaudeCredentialsBanner';
import { CommandPalette, spotlight } from '@/shared/components/CommandPalette';
import { ConnectionStatus } from '@/shared/components/ConnectionStatus';

interface NavSection {
  label: string;
  icon: Icon;
  items: { label: string; path: string; icon: Icon }[];
  defaultOpen?: boolean;
}

const navSections: NavSection[] = [
  {
    label: 'Core',
    icon: IconDashboard,
    defaultOpen: true,
    items: [
      { label: 'Dashboard', path: '/', icon: IconDashboard },
      { label: 'Chat', path: '/chat', icon: IconMessageCircle },
      { label: 'Threads', path: '/threads', icon: IconMessages },
      { label: 'Work Items', path: '/work-items', icon: IconListCheck },
      { label: 'Boards', path: '/boards', icon: IconLayoutKanban },
    ],
  },
  {
    label: 'Development',
    icon: IconCode,
    defaultOpen: true,
    items: [
      { label: 'Workflows', path: '/workflows', icon: IconGitBranch },
      { label: 'Pipelines', path: '/pipelines', icon: IconPlayerPlay },
      { label: 'Repositories', path: '/repositories', icon: IconFolder },
      { label: 'Sandboxes', path: '/sandboxes', icon: IconBox },
      { label: 'Artifacts', path: '/artifacts', icon: IconPackage },
      { label: 'Test Results', path: '/test-results', icon: IconTestPipe2 },
      { label: 'Debug', path: '/debug', icon: IconBug },
    ],
  },
  {
    label: 'Scheduling',
    icon: IconCalendarEvent,
    items: [
      { label: 'Automations', path: '/automations', icon: IconCalendarEvent },
    ],
  },
  {
    label: 'AI & Agents',
    icon: IconRobot,
    items: [
      { label: 'Agents', path: '/agents', icon: IconRobot },
      { label: 'Skills', path: '/skills', icon: IconCode },
      { label: 'AI Providers', path: '/ai-providers', icon: IconBrain },
      { label: 'Models', path: '/models', icon: IconCpu },
      { label: 'MCP Servers', path: '/mcp-servers', icon: IconPlug },
    ],
  },
  {
    label: 'Compliance',
    icon: IconShieldCheck,
    items: [
      { label: 'Overview', path: '/compliance', icon: IconShieldCheck },
      { label: 'Regulations', path: '/compliance/regulations', icon: IconShieldCheck },
      { label: 'Policies', path: '/compliance/policies', icon: IconFileText },
      { label: 'Procedures', path: '/compliance/procedures', icon: IconListDetails },
      { label: 'Practices', path: '/compliance/practices', icon: IconTool },
      { label: 'ADRs', path: '/compliance/architecture-decisions', icon: IconBulb },
    ],
  },
  {
    label: 'Experimentation',
    icon: IconFlask,
    items: [
      { label: 'Strategies', path: '/experimentation/strategies', icon: IconTarget },
      { label: 'KPIs', path: '/experimentation/kpis', icon: IconChartBar },
      { label: 'Experiments', path: '/experimentation/experiments', icon: IconFlask },
      { label: 'Metrics', path: '/experimentation/metrics', icon: IconChartBar },
    ],
  },
  {
    label: 'Knowledge',
    icon: IconBrain,
    items: [
      { label: 'Knowledge Base', path: '/knowledge', icon: IconBrain },
    ],
  },
  {
    label: 'Configuration',
    icon: IconSettings,
    items: [
      { label: 'Projects', path: '/projects', icon: IconBriefcase },
      { label: 'Environments', path: '/environments', icon: IconServer },
      { label: 'Variables', path: '/variables', icon: IconVariable },
      { label: 'Credentials', path: '/credentials', icon: IconLock },
      { label: 'Triggers', path: '/triggers', icon: IconBolt },
      { label: 'Policies', path: '/policies', icon: IconLock },
      { label: 'Notifications', path: '/notifications', icon: IconBell },
    ],
  },
  {
    label: 'Administration',
    icon: IconShield,
    items: [
      { label: 'Users', path: '/users', icon: IconUsers },
      { label: 'Teams', path: '/teams', icon: IconUsersGroup },
      { label: 'Approvals', path: '/approvals', icon: IconCheckbox },
      { label: 'Security', path: '/security', icon: IconShield },
      { label: 'PII Stats', path: '/pii-stats', icon: IconFingerprint },
      { label: 'Events', path: '/events', icon: IconTimeline },
      { label: 'Audit', path: '/audit', icon: IconHistory },
      { label: 'Channels', path: '/settings/channels', icon: IconPlug },
      { label: 'Settings', path: '/settings', icon: IconSettings },
    ],
  },
];

function NavSectionGroup({
  section,
  collapsed,
  onNavigate,
}: {
  section: NavSection;
  collapsed: boolean;
  onNavigate: (path: string) => void;
}) {
  const location = useLocation();
  const isActive = section.items.some((item) => location.pathname === item.path);
  const [opened, setOpened] = useState(section.defaultOpen || isActive);

  useEffect(() => {
    if (isActive && !opened) setOpened(true);
  }, [isActive]); // eslint-disable-line react-hooks/exhaustive-deps

  if (collapsed) {
    return (
      <Tooltip label={section.label} position="right" withArrow>
        <ActionIcon
          variant={isActive ? 'light' : 'subtle'}
          color={isActive ? 'indigo' : 'gray'}
          size="lg"
          my={2}
          mx="auto"
          style={{ display: 'block' }}
          onClick={() => {
            if (section.items.length === 1) {
              onNavigate(section.items[0]!.path);
            }
          }}
        >
          <section.icon size={20} stroke={1.5} />
        </ActionIcon>
      </Tooltip>
    );
  }

  return (
    <Box mb={2}>
      <UnstyledButton
        onClick={() => setOpened((o) => !o)}
        py={6}
        px="sm"
        style={{
          display: 'flex',
          alignItems: 'center',
          width: '100%',
          borderRadius: 'var(--mantine-radius-sm)',
          gap: 8,
        }}
      >
        <section.icon
          size={16}
          stroke={1.5}
          style={{
            color: isActive
              ? 'var(--mantine-color-indigo-5)'
              : 'var(--mantine-color-dimmed)',
            flexShrink: 0,
          }}
        />
        <Text
          size="xs"
          fw={700}
          tt="uppercase"
          c={isActive ? 'indigo.4' : 'dimmed'}
          style={{ flex: 1, letterSpacing: '0.05em' }}
        >
          {section.label}
        </Text>
        <IconChevronRight
          size={14}
          stroke={1.5}
          style={{
            color: 'var(--mantine-color-dimmed)',
            transform: opened ? 'rotate(90deg)' : 'none',
            transition: 'transform 200ms ease',
          }}
        />
      </UnstyledButton>
      <Collapse in={opened}>
        <Box pl={4}>
          {section.items.map((item) => (
            <NavLink
              key={item.path}
              label={item.label}
              leftSection={<item.icon size={16} stroke={1.5} />}
              active={location.pathname === item.path}
              onClick={() => onNavigate(item.path)}
              py={5}
              px="sm"
              style={{
                borderRadius: 'var(--mantine-radius-sm)',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

export function AppLayout() {
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure();
  const [navCollapsed, setNavCollapsed] = useLocalStorage({
    key: 'lintel-nav-collapsed',
    defaultValue: false,
  });
  const navigate = useNavigate();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  useHotkeys([
    ['mod+b', () => setNavCollapsed((c) => !c)],
  ]);

  const handleNavigate = (path: string) => {
    void navigate(path);
    closeMobile();
  };

  return (
    <AppShell
      header={{ height: 52 }}
      navbar={{
        width: navCollapsed ? 60 : 240,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened },
      }}
      padding="md"
      transitionDuration={200}
      transitionTimingFunction="ease"
    >
      <AppShell.Header
        style={{
          borderBottom: '1px solid var(--mantine-color-default-border)',
          backdropFilter: 'blur(10px)',
          backgroundColor: colorScheme === 'dark'
            ? 'rgba(26, 27, 30, 0.85)'
            : 'rgba(255, 255, 255, 0.85)',
        }}
      >
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="sm"
              size="sm"
            />
            <Group gap={6}>
              <Box
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background:
                    'linear-gradient(135deg, var(--mantine-color-indigo-5), var(--mantine-color-violet-5))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text size="sm" fw={800} c="white" style={{ lineHeight: 1 }}>
                  L
                </Text>
              </Box>
              {!navCollapsed && (
                <Title order={4} fw={700} style={{ letterSpacing: '-0.02em' }}>
                  Lintel
                </Title>
              )}
            </Group>
          </Group>
          <Group gap="xs">
            <Tooltip
              label={
                <>
                  <Kbd size="xs">Ctrl</Kbd> + <Kbd size="xs">K</Kbd>
                </>
              }
            >
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={() => spotlight.open()}
                aria-label="Search"
              >
                <IconSearch size={18} />
              </ActionIcon>
            </Tooltip>
            <ClaudeCredentialsBanner />
            <ConnectionStatus />
            <ActionIcon
              variant="subtle"
              color="gray"
              size="lg"
              onClick={toggleColorScheme}
              aria-label="Toggle color scheme"
            >
              {colorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        style={{
          borderRight: '1px solid var(--mantine-color-default-border)',
          transition: 'width 200ms ease',
        }}
      >
        <AppShell.Section grow component={ScrollArea} scrollbarSize={4} p={navCollapsed ? 4 : 'xs'}>
          {navSections.map((section) => (
            <NavSectionGroup
              key={section.label}
              section={section}
              collapsed={navCollapsed}
              onNavigate={handleNavigate}
            />
          ))}
        </AppShell.Section>

        <AppShell.Section style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
          <Tooltip
            label={navCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            position="right"
            withArrow
          >
            <UnstyledButton
              onClick={() => setNavCollapsed((c) => !c)}
              p="sm"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: navCollapsed ? 'center' : 'flex-start',
                gap: 8,
                width: '100%',
                opacity: 0.6,
                transition: 'opacity 150ms',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = '1';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '0.6';
              }}
            >
              {navCollapsed ? (
                <IconLayoutSidebarLeftExpand size={18} stroke={1.5} />
              ) : (
                <>
                  <IconLayoutSidebarLeftCollapse size={18} stroke={1.5} />
                  <Text size="xs" c="dimmed">
                    Collapse
                  </Text>
                  <Kbd size="xs" ml="auto" style={{ opacity: 0.6 }}>
                    Ctrl+B
                  </Kbd>
                </>
              )}
            </UnstyledButton>
          </Tooltip>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
      <CommandPalette />
    </AppShell>
  );
}
