import { useState, useMemo } from 'react';
import {
  Stack,
  Title,
  Text,
  Tabs,
  Select,
  Loader,
  Center,
} from '@mantine/core';
import {
  IconTopologyStarRing3,
  IconListDetails,
  IconChartDots3,
  IconBug,
} from '@tabler/icons-react';
import { EmptyState } from '@/shared/components/EmptyState';
import {
  useListIntegrationMaps,
  useGetIntegrationMapGraph,
  useGetIntegrationMapPatterns,
  useGetIntegrationMapAntipatterns,
  useGetIntegrationMapCouplingScores,
} from '../hooks/useIntegrationMap';
import { ServiceDependencyGraph } from '../components/ServiceDependencyGraph';
import { IntegrationCatalogue } from '../components/IntegrationCatalogue';
import { CouplingScoresTable } from '../components/CouplingScoresTable';
import { AntipatternsList } from '../components/AntipatternsList';

export function Component() {
  const [selectedMapId, setSelectedMapId] = useState<string | null>(null);

  // Fetch all integration maps
  const {
    data: maps,
    isLoading: mapsLoading,
  } = useListIntegrationMaps();

  // Determine the active map: user selection or first available
  const activeMapId = selectedMapId ?? maps?.[0]?.map_id ?? '';

  // Select options
  const mapOptions = useMemo(
    () =>
      (maps ?? []).map((m) => ({
        value: m.map_id,
        label: `${m.repository_id} - ${m.status} (${new Date(m.created_at).toLocaleDateString()})`,
      })),
    [maps],
  );

  // Data queries for the active map
  const { data: graphData, isLoading: graphLoading } =
    useGetIntegrationMapGraph(activeMapId);
  const { data: patterns, isLoading: patternsLoading } =
    useGetIntegrationMapPatterns(activeMapId);
  const { data: antipatterns, isLoading: antipatternsLoading } =
    useGetIntegrationMapAntipatterns(activeMapId);
  const { data: couplingScores, isLoading: couplingLoading } =
    useGetIntegrationMapCouplingScores(activeMapId);

  // Loading state for the page
  if (mapsLoading) {
    return (
      <Center py="xl">
        <Loader size="lg" />
      </Center>
    );
  }

  // Empty state when no maps exist
  if (!maps || maps.length === 0) {
    return (
      <Stack gap="lg">
        <div>
          <Title order={2}>Integration Patterns</Title>
          <Text c="dimmed" size="sm" mt={4}>
            Visualise service dependencies, discover integration patterns, and
            detect anti-patterns across your repositories.
          </Text>
        </div>
        <EmptyState
          title="No Integration Maps"
          description="Run an integration analysis workflow on a repository to generate an integration map."
        />
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <div>
        <Title order={2}>Integration Patterns</Title>
        <Text c="dimmed" size="sm" mt={4}>
          Visualise service dependencies, discover integration patterns, and
          detect anti-patterns across your repositories.
        </Text>
      </div>

      {mapOptions.length > 1 && (
        <Select
          label="Integration Map"
          placeholder="Select a map"
          data={mapOptions}
          value={activeMapId}
          onChange={(val) => setSelectedMapId(val)}
          w={400}
        />
      )}

      <Tabs defaultValue="graph">
        <Tabs.List>
          <Tabs.Tab
            value="graph"
            leftSection={<IconTopologyStarRing3 size={16} />}
          >
            Dependency Graph
          </Tabs.Tab>
          <Tabs.Tab
            value="catalogue"
            leftSection={<IconListDetails size={16} />}
          >
            Pattern Catalogue
          </Tabs.Tab>
          <Tabs.Tab
            value="coupling"
            leftSection={<IconChartDots3 size={16} />}
          >
            Coupling Scores
          </Tabs.Tab>
          <Tabs.Tab value="antipatterns" leftSection={<IconBug size={16} />}>
            Anti-patterns
          </Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="graph" pt="md">
          {graphLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : graphData &&
            graphData.nodes.length > 0 ? (
            <ServiceDependencyGraph
              nodes={graphData.nodes}
              edges={graphData.edges}
            />
          ) : (
            <EmptyState
              title="No Graph Data"
              description="The integration map does not contain any service nodes yet."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="catalogue" pt="md">
          {patternsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : patterns && patterns.length > 0 ? (
            <IntegrationCatalogue patterns={patterns} />
          ) : (
            <EmptyState
              title="No Patterns"
              description="No integration patterns have been catalogued for this map."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="coupling" pt="md">
          {couplingLoading || graphLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : couplingScores && couplingScores.length > 0 ? (
            <CouplingScoresTable
              scores={couplingScores}
              nodes={graphData?.nodes ?? []}
            />
          ) : (
            <EmptyState
              title="No Coupling Data"
              description="Coupling scores have not been computed for this integration map."
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="antipatterns" pt="md">
          {antipatternsLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : antipatterns ? (
            <AntipatternsList antipatterns={antipatterns} />
          ) : (
            <EmptyState
              title="No Anti-pattern Data"
              description="Anti-pattern detection has not been run for this integration map."
            />
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
