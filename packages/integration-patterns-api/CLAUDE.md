# lintel-integration-patterns-api

Integration pattern mapping, service graph, coupling analysis, and antipattern detection REST API routes and in-memory stores.

## Structure

- `src/lintel/integration_patterns_api/types.py` -- Frozen dataclasses: IntegrationMap, ServiceNode, IntegrationEdge, PatternCatalogueEntry, AntipatternDetection, ServiceCouplingScore
- `src/lintel/integration_patterns_api/store.py` -- InMemoryIntegrationPatternStore with async CRUD methods
- `src/lintel/integration_patterns_api/routes.py` -- FastAPI router + request/response models
- `src/lintel/integration_patterns_api/events.py` -- Event type constants for domain event publishing

## Entities

- **IntegrationMap** -- Top-level entity representing a mapping of service integrations for a repository/workflow run
- **ServiceNode** -- A service in the integration graph (language, metadata)
- **IntegrationEdge** -- A connection between two service nodes (protocol, integration type)
- **PatternCatalogueEntry** -- A detected integration pattern (e.g. saga, gateway, pub-sub)
- **AntipatternDetection** -- A detected antipattern with severity and affected nodes
- **ServiceCouplingScore** -- Coupling metrics per service node (afferent/efferent coupling, instability)

## Events

- `IntegrationMapCreated` -- Fired when a new integration map is created
- `IntegrationMapStatusUpdated` -- Fired when a map's status changes

## Testing

```bash
make test-integration-patterns-api
# or
uv run pytest packages/integration-patterns-api/tests/ -v
```

## DI Pattern

Uses `StoreProvider` from `lintel-api-support`. The app wires the real store at startup:
```python
from lintel.integration_patterns_api.routes import integration_pattern_store_provider
integration_pattern_store_provider.override(stores["integration_patterns"])
```
