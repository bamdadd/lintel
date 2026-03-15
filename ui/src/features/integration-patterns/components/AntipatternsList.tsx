import { useMemo } from 'react';
import { Accordion, Badge, Group, Stack, Text, Paper } from '@mantine/core';
import {
  IconAlertTriangle,
  IconAlertCircle,
  IconInfoCircle,
  IconAlertOctagon,
} from '@tabler/icons-react';
import type { AntipatternDetection } from '../types';

interface AntipatternsListProps {
  antipatterns: AntipatternDetection[];
}

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'] as const;

const SEVERITY_CONFIG: Record<
  string,
  { color: string; icon: React.ElementType }
> = {
  critical: { color: 'red', icon: IconAlertOctagon },
  high: { color: 'orange', icon: IconAlertTriangle },
  medium: { color: 'yellow', icon: IconAlertCircle },
  low: { color: 'blue', icon: IconInfoCircle },
};

export function AntipatternsList({ antipatterns }: AntipatternsListProps) {
  const grouped = useMemo(() => {
    const map = new Map<string, AntipatternDetection[]>();
    for (const sev of SEVERITY_ORDER) {
      map.set(sev, []);
    }
    for (const ap of antipatterns) {
      const key = SEVERITY_ORDER.includes(
        ap.severity as (typeof SEVERITY_ORDER)[number],
      )
        ? ap.severity
        : 'low';
      map.get(key)!.push(ap);
    }
    return map;
  }, [antipatterns]);

  if (antipatterns.length === 0) {
    return (
      <Paper withBorder p="md" radius="md">
        <Text c="dimmed" size="sm" ta="center" py="lg">
          No anti-patterns detected.
        </Text>
      </Paper>
    );
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Text fw={600} mb="md">
        Anti-pattern Detections
      </Text>

      <Accordion variant="separated">
        {SEVERITY_ORDER.map((severity) => {
          const items = grouped.get(severity) ?? [];
          if (items.length === 0) return null;

          const config = SEVERITY_CONFIG[severity]!;
          const Icon = config.icon;

          return (
            <Accordion.Item key={severity} value={severity}>
              <Accordion.Control>
                <Group gap="sm">
                  <Icon size={18} color={`var(--mantine-color-${config.color}-6)`} />
                  <Text fw={500} tt="capitalize">
                    {severity}
                  </Text>
                  <Badge color={config.color} size="sm" variant="light">
                    {items.length}
                  </Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="md">
                  {items.map((ap) => (
                    <Paper key={ap.detection_id} withBorder p="sm" radius="sm">
                      <Group justify="space-between" mb="xs">
                        <Text size="sm" fw={600}>
                          {ap.antipattern_type}
                        </Text>
                        <Badge
                          color={config.color}
                          size="xs"
                          variant="filled"
                        >
                          {severity}
                        </Badge>
                      </Group>
                      <Text size="sm" c="dimmed" mb="xs">
                        {ap.description}
                      </Text>
                      {ap.affected_nodes.length > 0 && (
                        <Group gap="xs">
                          <Text size="xs" c="dimmed">
                            Affected:
                          </Text>
                          {ap.affected_nodes.map((nodeId) => (
                            <Badge
                              key={nodeId}
                              size="xs"
                              variant="outline"
                              color="gray"
                            >
                              {nodeId}
                            </Badge>
                          ))}
                        </Group>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          );
        })}
      </Accordion>
    </Paper>
  );
}
