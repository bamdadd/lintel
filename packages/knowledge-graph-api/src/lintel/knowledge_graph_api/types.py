"""Knowledge graph domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class GraphNode:
    """A node in the knowledge graph (service, database, schema, queue, etc.)."""

    id: str
    kind: str  # "service", "database", "schema", "queue", "topic", "api"
    name: str
    repo_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge in the knowledge graph."""

    source_id: str
    target_id: str
    relation: str  # "publishes", "consumes", "reads", "writes", "calls", "owns"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Flow:
    """A discovered event/data flow across services."""

    id: str
    name: str
    source_service: str
    target_service: str
    event_type: str = ""
    transport: str = ""  # "kafka", "http", "grpc", "nats", etc.
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Schema:
    """A discovered database schema or data model."""

    id: str
    name: str
    repo_id: str = ""
    schema_type: str = ""  # "postgres", "mongo", "protobuf", "avro", "json"
    tables: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning repositories for the knowledge graph."""

    id: str
    status: str = "pending"  # "pending", "running", "completed", "failed"
    repo_ids: tuple[str, ...] = ()
    nodes_discovered: int = 0
    edges_discovered: int = 0
    flows_discovered: int = 0
    schemas_discovered: int = 0
    error: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""


@dataclass(frozen=True)
class KnowledgeGraph:
    """The full knowledge graph."""

    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    flows: tuple[Flow, ...] = ()
    schemas: tuple[Schema, ...] = ()
    scan_id: str = ""
