"""Tests for process mining domain types."""

from lintel.process_mining_api.types import (
    FlowDiagram,
    FlowEntry,
    FlowMetrics,
    FlowStep,
    FlowType,
    ProcessFlowMap,
    StepType,
)


def test_flow_type_values() -> None:
    assert FlowType.HTTP_REQUEST == "http_request"
    assert FlowType.EVENT_SOURCING == "event_sourcing"
    assert FlowType.COMMAND_DISPATCH == "command_dispatch"


def test_step_type_values() -> None:
    assert StepType.ENTRYPOINT == "entrypoint"
    assert StepType.DATABASE == "database"
    assert StepType.EVENT_BUS == "event_bus"


def test_flow_step_frozen() -> None:
    step = FlowStep(
        file_path="routes.py",
        function_name="create_user",
        line_number=42,
        step_type="handler",
    )
    assert step.file_path == "routes.py"
    assert step.line_number == 42


def test_flow_entry_defaults() -> None:
    source = FlowStep(file_path="a.py", function_name="f", line_number=1, step_type="entrypoint")
    entry = FlowEntry(
        flow_id="f1",
        flow_map_id="m1",
        flow_type="http_request",
        name="POST /users",
        source=source,
    )
    assert entry.steps == ()
    assert entry.sink is None
    assert entry.metadata == {}


def test_flow_diagram_frozen() -> None:
    d = FlowDiagram(
        diagram_id="d1",
        flow_map_id="m1",
        flow_type="http_request",
        title="HTTP Request Flow",
        mermaid_source="sequenceDiagram\n    A->>B: call",
    )
    assert "sequenceDiagram" in d.mermaid_source


def test_flow_metrics_defaults() -> None:
    m = FlowMetrics(metrics_id="x1", flow_map_id="m1", total_flows=5)
    assert m.avg_depth == 0.0
    assert m.flows_by_type == {}


def test_process_flow_map() -> None:
    fm = ProcessFlowMap(
        flow_map_id="m1",
        repository_id="r1",
        workflow_run_id="w1",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assert fm.status == "pending"
