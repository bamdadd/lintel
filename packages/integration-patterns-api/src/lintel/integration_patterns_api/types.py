"""Integration pattern domain types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntegrationMap:
    """Top-level entity representing a service integration mapping."""

    map_id: str
    repository_id: str
    workflow_run_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ServiceNode:
    """A service node in the integration graph."""

    node_id: str
    integration_map_id: str
    service_name: str
    language: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IntegrationEdge:
    """A directed edge between two service nodes."""

    edge_id: str
    integration_map_id: str
    source_node_id: str
    target_node_id: str
    integration_type: str
    protocol: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PatternCatalogueEntry:
    """A detected integration pattern entry."""

    entry_id: str
    integration_map_id: str
    pattern_type: str
    pattern_name: str
    occurrences: int
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AntipatternDetection:
    """A detected integration antipattern."""

    detection_id: str
    integration_map_id: str
    antipattern_type: str
    severity: str
    affected_nodes: list[str] = field(default_factory=list)
    description: str = ""


@dataclass(frozen=True)
class ServiceCouplingScore:
    """Coupling metrics for a service node."""

    score_id: str
    integration_map_id: str
    service_node_id: str
    afferent_coupling: int
    efferent_coupling: int
    instability: float
    computed_at: str
    service_name: str = ""
    weighted_afferent: float = 0.0
    weighted_efferent: float = 0.0
    weighted_instability: float = 0.0
    resilience_score: float = 1.0
