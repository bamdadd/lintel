export { Component } from './pages/IntegrationPatternsPage';
export { ServiceDependencyGraph } from './components/ServiceDependencyGraph';
export { IntegrationCatalogue } from './components/IntegrationCatalogue';
export { CouplingScoresTable } from './components/CouplingScoresTable';
export { AntipatternsList } from './components/AntipatternsList';
export {
  useListIntegrationMaps,
  useGetIntegrationMap,
  useGetIntegrationMapGraph,
  useGetIntegrationMapPatterns,
  useGetIntegrationMapAntipatterns,
  useGetIntegrationMapCouplingScores,
  useCreateIntegrationMap,
} from './hooks/useIntegrationMap';
export type {
  IntegrationMap,
  ServiceNode,
  IntegrationEdge,
  PatternCatalogueEntry,
  AntipatternDetection,
  ServiceCouplingScore,
  GraphData,
} from './types';
