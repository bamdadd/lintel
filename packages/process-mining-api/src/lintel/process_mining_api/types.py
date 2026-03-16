"""Process mining / data flow mapping domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FlowType(StrEnum):
    """Categories of data/process flows discovered in a codebase."""

    HTTP_REQUEST = "http_request"
    EVENT_SOURCING = "event_sourcing"
    COMMAND_DISPATCH = "command_dispatch"
    BACKGROUND_JOB = "background_job"
    EXTERNAL_INTEGRATION = "external_integration"


class StepType(StrEnum):
    """Role a step plays in a flow."""

    ENTRYPOINT = "entrypoint"
    MIDDLEWARE = "middleware"
    HANDLER = "handler"
    SERVICE = "service"
    STORE = "store"
    DATABASE = "database"
    EVENT_BUS = "event_bus"
    PROJECTION = "projection"
    EXTERNAL_API = "external_api"
    MESSAGE_QUEUE = "message_queue"
    SCHEDULER = "scheduler"


@dataclass(frozen=True)
class FlowStep:
    """A single hop in a traced data flow."""

    file_path: str
    function_name: str
    line_number: int
    step_type: str
    description: str = ""


@dataclass(frozen=True)
class FlowEntry:
    """An individual traced flow: source -> intermediate steps -> sink."""

    flow_id: str
    flow_map_id: str
    flow_type: str
    name: str
    source: FlowStep
    steps: tuple[FlowStep, ...] = ()
    sink: FlowStep | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowDiagram:
    """A Mermaid diagram covering flows of one type."""

    diagram_id: str
    flow_map_id: str
    flow_type: str
    title: str
    mermaid_source: str
    flow_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlowMetrics:
    """Aggregate metrics for a process mining run."""

    metrics_id: str
    flow_map_id: str
    total_flows: int
    flows_by_type: dict[str, int] = field(default_factory=dict)
    avg_depth: float = 0.0
    max_depth: int = 0
    complexity_score: float = 0.0


@dataclass(frozen=True)
class ProcessFlowMap:
    """Top-level entity representing a process mining analysis run."""

    flow_map_id: str
    repository_id: str
    workflow_run_id: str
    status: str
    created_at: str
    updated_at: str
