"""In-memory store for integration pattern entities."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.integration_patterns_api.types import (
        AntipatternDetection,
        IntegrationEdge,
        IntegrationMap,
        PatternCatalogueEntry,
        ServiceCouplingScore,
        ServiceNode,
    )


class InMemoryIntegrationPatternStore:
    """In-memory store for integration maps and related entities."""

    def __init__(self) -> None:
        self._maps: dict[str, IntegrationMap] = {}
        self._nodes: dict[str, list[ServiceNode]] = {}
        self._edges: dict[str, list[IntegrationEdge]] = {}
        self._patterns: dict[str, list[PatternCatalogueEntry]] = {}
        self._antipatterns: dict[str, list[AntipatternDetection]] = {}
        self._coupling_scores: dict[str, list[ServiceCouplingScore]] = {}

    # --- Integration maps ---

    async def create_map(self, map: IntegrationMap) -> None:  # noqa: A002
        self._maps[map.map_id] = map

    async def get_map(self, map_id: str) -> IntegrationMap | None:
        return self._maps.get(map_id)

    async def list_maps(
        self,
        *,
        repository_id: str | None = None,
    ) -> list[IntegrationMap]:
        maps = list(self._maps.values())
        if repository_id is not None:
            maps = [m for m in maps if m.repository_id == repository_id]
        return maps

    async def update_map_status(self, map_id: str, status: str) -> None:
        existing = self._maps.get(map_id)
        if existing is not None:
            self._maps[map_id] = replace(existing, status=status)

    # --- Service nodes ---

    async def add_nodes(self, nodes: list[ServiceNode]) -> None:
        for node in nodes:
            self._nodes.setdefault(node.integration_map_id, []).append(node)

    async def get_nodes(self, integration_map_id: str) -> list[ServiceNode]:
        return list(self._nodes.get(integration_map_id, []))

    # --- Integration edges ---

    async def add_edges(self, edges: list[IntegrationEdge]) -> None:
        for edge in edges:
            self._edges.setdefault(edge.integration_map_id, []).append(edge)

    async def get_edges(self, integration_map_id: str) -> list[IntegrationEdge]:
        return list(self._edges.get(integration_map_id, []))

    # --- Pattern catalogue entries ---

    async def add_patterns(self, patterns: list[PatternCatalogueEntry]) -> None:
        for pattern in patterns:
            self._patterns.setdefault(pattern.integration_map_id, []).append(pattern)

    async def get_patterns(self, integration_map_id: str) -> list[PatternCatalogueEntry]:
        return list(self._patterns.get(integration_map_id, []))

    # --- Antipattern detections ---

    async def add_antipatterns(self, detections: list[AntipatternDetection]) -> None:
        for detection in detections:
            self._antipatterns.setdefault(detection.integration_map_id, []).append(detection)

    async def get_antipatterns(self, integration_map_id: str) -> list[AntipatternDetection]:
        return list(self._antipatterns.get(integration_map_id, []))

    # --- Service coupling scores ---

    async def add_coupling_scores(self, scores: list[ServiceCouplingScore]) -> None:
        for score in scores:
            self._coupling_scores.setdefault(score.integration_map_id, []).append(score)

    async def get_coupling_scores(self, integration_map_id: str) -> list[ServiceCouplingScore]:
        return list(self._coupling_scores.get(integration_map_id, []))
