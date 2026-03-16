"""In-memory store for process mining entities."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.process_mining_api.types import (
        FlowDiagram,
        FlowEntry,
        FlowMetrics,
        ProcessFlowMap,
    )


class InMemoryProcessMiningStore:
    """In-memory store for process flow maps and related entities."""

    def __init__(self) -> None:
        self._maps: dict[str, ProcessFlowMap] = {}
        self._flows: dict[str, list[FlowEntry]] = {}
        self._diagrams: dict[str, list[FlowDiagram]] = {}
        self._metrics: dict[str, FlowMetrics] = {}

    # --- Flow maps ---

    async def create_map(self, flow_map: ProcessFlowMap) -> None:
        self._maps[flow_map.flow_map_id] = flow_map

    async def get_map(self, flow_map_id: str) -> ProcessFlowMap | None:
        return self._maps.get(flow_map_id)

    async def list_maps(
        self,
        *,
        repository_id: str | None = None,
    ) -> list[ProcessFlowMap]:
        maps = list(self._maps.values())
        if repository_id is not None:
            maps = [m for m in maps if m.repository_id == repository_id]
        return maps

    async def update_map_status(self, flow_map_id: str, status: str) -> None:
        existing = self._maps.get(flow_map_id)
        if existing is not None:
            self._maps[flow_map_id] = replace(existing, status=status)

    # --- Flow entries ---

    async def add_flows(self, flows: list[FlowEntry]) -> None:
        for flow in flows:
            self._flows.setdefault(flow.flow_map_id, []).append(flow)

    async def get_flows(
        self,
        flow_map_id: str,
        *,
        flow_type: str | None = None,
    ) -> list[FlowEntry]:
        entries = list(self._flows.get(flow_map_id, []))
        if flow_type is not None:
            entries = [e for e in entries if e.flow_type == flow_type]
        return entries

    # --- Diagrams ---

    async def add_diagrams(self, diagrams: list[FlowDiagram]) -> None:
        for diagram in diagrams:
            self._diagrams.setdefault(diagram.flow_map_id, []).append(diagram)

    async def get_diagrams(
        self,
        flow_map_id: str,
        *,
        flow_type: str | None = None,
    ) -> list[FlowDiagram]:
        entries = list(self._diagrams.get(flow_map_id, []))
        if flow_type is not None:
            entries = [e for e in entries if e.flow_type == flow_type]
        return entries

    # --- Metrics ---

    async def set_metrics(self, metrics: FlowMetrics) -> None:
        self._metrics[metrics.flow_map_id] = metrics

    async def get_metrics(self, flow_map_id: str) -> FlowMetrics | None:
        return self._metrics.get(flow_map_id)
