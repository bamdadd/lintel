"""Tests for InMemoryIntegrationPatternStore."""

from __future__ import annotations

from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore
from lintel.integration_patterns_api.types import (
    AntipatternDetection,
    IntegrationEdge,
    IntegrationMap,
    PatternCatalogueEntry,
    ServiceCouplingScore,
    ServiceNode,
)


def _make_map(
    map_id: str = "map-1",
    repository_id: str = "repo-1",
    workflow_run_id: str = "run-1",
    status: str = "pending",
) -> IntegrationMap:
    return IntegrationMap(
        map_id=map_id,
        repository_id=repository_id,
        workflow_run_id=workflow_run_id,
        status=status,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


async def test_create_and_get_map() -> None:
    store = InMemoryIntegrationPatternStore()
    m = _make_map()
    await store.create_map(m)
    result = await store.get_map("map-1")
    assert result is not None
    assert result.map_id == "map-1"
    assert result.repository_id == "repo-1"
    assert result.status == "pending"


async def test_list_maps_empty() -> None:
    store = InMemoryIntegrationPatternStore()
    result = await store.list_maps()
    assert result == []


async def test_list_maps_filter_by_repository_id() -> None:
    store = InMemoryIntegrationPatternStore()
    await store.create_map(_make_map(map_id="m1", repository_id="repo-a"))
    await store.create_map(_make_map(map_id="m2", repository_id="repo-b"))
    await store.create_map(_make_map(map_id="m3", repository_id="repo-a"))

    result = await store.list_maps(repository_id="repo-a")
    assert len(result) == 2
    assert {m.map_id for m in result} == {"m1", "m3"}

    result_all = await store.list_maps()
    assert len(result_all) == 3


async def test_update_map_status() -> None:
    store = InMemoryIntegrationPatternStore()
    await store.create_map(_make_map())
    await store.update_map_status("map-1", "completed")
    result = await store.get_map("map-1")
    assert result is not None
    assert result.status == "completed"


async def test_add_and_get_nodes() -> None:
    store = InMemoryIntegrationPatternStore()
    nodes = [
        ServiceNode(
            node_id="n1",
            integration_map_id="map-1",
            service_name="service-a",
            language="python",
        ),
        ServiceNode(
            node_id="n2",
            integration_map_id="map-1",
            service_name="service-b",
            language="go",
        ),
    ]
    await store.add_nodes(nodes)
    result = await store.get_nodes("map-1")
    assert len(result) == 2
    assert result[0].node_id == "n1"
    assert result[1].service_name == "service-b"

    empty = await store.get_nodes("nonexistent")
    assert empty == []


async def test_add_and_get_edges() -> None:
    store = InMemoryIntegrationPatternStore()
    edges = [
        IntegrationEdge(
            edge_id="e1",
            integration_map_id="map-1",
            source_node_id="n1",
            target_node_id="n2",
            integration_type="sync",
            protocol="http",
        ),
    ]
    await store.add_edges(edges)
    result = await store.get_edges("map-1")
    assert len(result) == 1
    assert result[0].edge_id == "e1"
    assert result[0].protocol == "http"

    empty = await store.get_edges("nonexistent")
    assert empty == []


async def test_add_and_get_patterns() -> None:
    store = InMemoryIntegrationPatternStore()
    patterns = [
        PatternCatalogueEntry(
            entry_id="p1",
            integration_map_id="map-1",
            pattern_type="structural",
            pattern_name="saga",
            occurrences=3,
        ),
    ]
    await store.add_patterns(patterns)
    result = await store.get_patterns("map-1")
    assert len(result) == 1
    assert result[0].pattern_name == "saga"
    assert result[0].occurrences == 3

    empty = await store.get_patterns("nonexistent")
    assert empty == []


async def test_add_and_get_antipatterns() -> None:
    store = InMemoryIntegrationPatternStore()
    detections = [
        AntipatternDetection(
            detection_id="ap1",
            integration_map_id="map-1",
            antipattern_type="circular_dependency",
            severity="high",
            affected_nodes=["n1", "n2"],
            description="Circular dependency detected",
        ),
    ]
    await store.add_antipatterns(detections)
    result = await store.get_antipatterns("map-1")
    assert len(result) == 1
    assert result[0].antipattern_type == "circular_dependency"
    assert result[0].severity == "high"
    assert result[0].affected_nodes == ["n1", "n2"]

    empty = await store.get_antipatterns("nonexistent")
    assert empty == []


async def test_add_and_get_coupling_scores() -> None:
    store = InMemoryIntegrationPatternStore()
    scores = [
        ServiceCouplingScore(
            score_id="cs1",
            integration_map_id="map-1",
            service_node_id="n1",
            afferent_coupling=5,
            efferent_coupling=3,
            instability=0.375,
            computed_at="2026-01-01T00:00:00Z",
        ),
    ]
    await store.add_coupling_scores(scores)
    result = await store.get_coupling_scores("map-1")
    assert len(result) == 1
    assert result[0].afferent_coupling == 5
    assert result[0].efferent_coupling == 3
    assert result[0].instability == 0.375

    empty = await store.get_coupling_scores("nonexistent")
    assert empty == []
