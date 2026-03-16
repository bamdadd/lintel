import { useState, useMemo } from 'react';
import {
  Stack,
  Title,
  Text,
  Tabs,
  Select,
  Loader,
  Center,
  Group,
} from '@mantine/core';
import {
  IconArrowsShuffle,
  IconChartDots3,
  IconCode,
  IconListDetails,
  IconTopologyStarRing3,
} from '@tabler/icons-react';
import { EmptyState } from '@/shared/components/EmptyState';
import {
  useListFlowMaps,
  useGetDiagrams,
  useGetFlows,
  useGetFlowMetrics,
} from '../hooks/useProcessMining';
import { FlowGraph } from '../components/FlowGraph';
import { MermaidDiagram } from '../components/MermaidDiagram';
import { FlowMetricsSummary } from '../components/FlowMetricsSummary';
import { FlowTable } from '../components/FlowTable';
import { FLOW_TYPE_LABELS } from '../types';

export function Component() {
  const [selectedMapId, setSelectedMapId] = useState<string | null>(null);
  const [flowTypeFilter, setFlowTypeFilter] = useState<string | null>(null);

  const { data: maps, isLoading: mapsLoading } = useListFlowMaps();

  const activeMapId = selectedMapId ?? maps?.[0]?.flow_map_id ?? '';

  const mapOptions = useMemo(
    () =>
      (maps ?? []).map((m) => ({
        value: m.flow_map_id,
        label: `${m.repository_id} — ${m.status} (${new Date(m.created_at).toLocaleDateString()})`,
      })),
    [maps],
  );

  const flowTypeOptions = useMemo(
    () => [
      { value: '', label: 'All types' },
      ...Object.entries(FLOW_TYPE_LABELS).map(([k, v]) => ({
        value: k,
        label: v,
      })),
    ],
    [],
  );

  const { data: diagrams, isLoading: diagramsLoading } = useGetDiagrams(
    activeMapId,
    flowTypeFilter || undefined,
  );
  const { data: flows, isLoading: flowsLoading } = useGetFlows(
    activeMapId,
    flowTypeFilter || undefined,
  );
  const { data: metrics, isLoading: metricsLoading } =
    useGetFlowMetrics(activeMapId);

  if (mapsLoading) {
    return (
      <Center py="xl">
        <Loader size="lg" />
      </Center>
    );
  }

  if (!maps || maps.length === 0) {
    return (
      <Stack gap="lg">
        <div>
          <Title order={2}>Process Mining</Title>
          <Text c="dimmed" size="sm" mt={4}>
            Discover data flows, trace request paths, and visualise how data
            moves through your codebase.
          </Text>
        </div>
        <EmptyState
          title="No Flow Maps"
          description="Run a Process Mining workflow on a repository to generate flow maps and diagrams."
        />
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Process Mining</Title>
        <Text c="dimmed" size="sm" mt={4}>
          Discover data flows, trace request paths, and visualise how data moves
          through your codebase.
        </Text>
      </div>

      <Group>
        {mapOptions.length > 1 && (
          <Select
            label="Flow Map"
            placeholder="Select a map"
            data={mapOptions}
            value={activeMapId}
            onChange={(val) => setSelectedMapId(val)}
            w={400}
          />
        )}
        <Select
          label="Flow Type"
          data={flowTypeOptions}
          value={flowTypeFilter ?? ''}
          onChange={(val) => setFlowTypeFilter(val || null)}
          w={220}
        />
      </Group>

      <Tabs defaultValue="graph">
        <Tabs.List>
          <Tabs.Tab
            value="graph"
            leftSection={<IconTopologyStarRing3 size={16} />}
          >
            Flow Graph
          </Tabs.Tab>
          <Tabs.Tab
            value="sequence"
            leftSection={<IconArrowsShuffle size={16} />}
          >
            Sequence Diagrams
          </Tabs.Tab>
          <Tabs.Tab
            value="flows"
            leftSection={<IconListDetails size={16} />}
          >
            Flows
          </Tabs.Tab>
          <Tabs.Tab
            value="metrics"
            leftSection={<IconChartDots3 size={16} />}
          >
            Metrics
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="graph" pt="md">
          {flowsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : flows && flows.length > 0 ? (
            <FlowGraph flows={flows} />
          ) : (
            <EmptyState
              title="No Flow Data"
              description="No traced flows found for this map. Run the Process Mining workflow to generate flow data."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="sequence" pt="md">
          {diagramsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : diagrams && diagrams.length > 0 ? (
            <Stack gap="lg">
              {diagrams.map((d) => (
                <MermaidDiagram
                  key={d.diagram_id}
                  source={d.mermaid_source}
                  title={d.title}
                />
              ))}
            </Stack>
          ) : (
            <EmptyState
              title="No Diagrams"
              description="No sequence diagrams have been generated for this map yet."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="flows" pt="md">
          {flowsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : flows && flows.length > 0 ? (
            <FlowTable flows={flows} />
          ) : (
            <EmptyState
              title="No Flows"
              description="No traced flows found for this map."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="metrics" pt="md">
          {metricsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : metrics && metrics.total_flows > 0 ? (
            <FlowMetricsSummary metrics={metrics} />
          ) : (
            <EmptyState
              title="No Metrics"
              description="Flow metrics have not been computed for this map."
            />
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
