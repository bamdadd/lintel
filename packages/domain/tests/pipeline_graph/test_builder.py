"""Tests for GraphBuilder."""

from __future__ import annotations

from lintel.domain.pipeline_graph.builder import GraphBuilder
from lintel.domain.pipeline_graph.models import EdgeType, NodeType
from lintel.workflows.types import PipelineRun, Stage, StageStatus, WorkflowDefinitionRecord


def _run_with_stages(*names: str, trigger_type: str = "chat:conv1") -> PipelineRun:
    stages = tuple(Stage(stage_id=name, name=name, stage_type=name) for name in names)
    return PipelineRun(
        run_id="run-1",
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="wf-1",
        stages=stages,
        trigger_type=trigger_type,
        trigger_id="trig-1",
    )


def _run_with_outputs() -> PipelineRun:
    stages = (
        Stage(stage_id="plan", name="plan", stage_type="plan"),
        Stage(
            stage_id="implement",
            name="implement",
            stage_type="implement",
            outputs={"diff": "some-diff"},
        ),
    )
    return PipelineRun(
        run_id="run-2",
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="wf-1",
        stages=stages,
        trigger_type="manual",
    )


# ------------------------------------------------------------------
# Basic linear pipeline
# ------------------------------------------------------------------


def test_build_creates_trigger_node() -> None:
    run = _run_with_stages("plan", "implement")
    graph = GraphBuilder(run).build()
    triggers = graph.nodes_by_type(NodeType.TRIGGER)
    assert len(triggers) == 1
    assert triggers[0].name == "chat:conv1"


def test_build_creates_stage_nodes() -> None:
    run = _run_with_stages("plan", "implement", "review")
    graph = GraphBuilder(run).build()
    stages = graph.nodes_by_type(NodeType.STAGE)
    assert len(stages) == 3


def test_trigger_edge_to_first_stage() -> None:
    run = _run_with_stages("plan")
    graph = GraphBuilder(run).build()
    trigger_edges = [e for e in graph.edges if e.edge_type == EdgeType.TRIGGER]
    assert len(trigger_edges) == 1
    assert trigger_edges[0].target_id == "stage-plan"


def test_linear_execution_edges() -> None:
    run = _run_with_stages("plan", "implement", "review")
    graph = GraphBuilder(run).build()
    exec_edges = [e for e in graph.edges if e.edge_type == EdgeType.EXECUTION]
    assert len(exec_edges) == 2
    assert exec_edges[0].source_id == "stage-plan"
    assert exec_edges[0].target_id == "stage-implement"
    assert exec_edges[1].source_id == "stage-implement"
    assert exec_edges[1].target_id == "stage-review"


def test_stage_metadata_includes_status() -> None:
    run = _run_with_stages("plan")
    graph = GraphBuilder(run).build()
    stage = graph.node_by_id("stage-plan")
    assert stage is not None
    assert stage.metadata["status"] == str(StageStatus.PENDING)


# ------------------------------------------------------------------
# Artifact nodes
# ------------------------------------------------------------------


def test_artifact_nodes_for_outputs() -> None:
    run = _run_with_outputs()
    graph = GraphBuilder(run).build()
    artifacts = graph.nodes_by_type(NodeType.ARTIFACT)
    assert len(artifacts) == 1
    assert artifacts[0].node_id == "artifact-implement"


def test_artifact_data_flow_edge() -> None:
    run = _run_with_outputs()
    graph = GraphBuilder(run).build()
    df_edges = [e for e in graph.edges if e.edge_type == EdgeType.DATA_FLOW]
    assert len(df_edges) == 1
    assert df_edges[0].source_id == "stage-implement"
    assert df_edges[0].target_id == "artifact-implement"
    assert df_edges[0].label == "produces"


def test_no_artifact_for_empty_outputs() -> None:
    run = _run_with_stages("plan")
    graph = GraphBuilder(run).build()
    assert len(graph.nodes_by_type(NodeType.ARTIFACT)) == 0


# ------------------------------------------------------------------
# Workflow definition edges
# ------------------------------------------------------------------


def _definition_with_edges() -> WorkflowDefinitionRecord:
    return WorkflowDefinitionRecord(
        definition_id="wf-1",
        name="feature",
        graph_edges=(("plan", "implement"), ("implement", "review")),
        entry_point="plan",
    )


def test_definition_edges_override_linear() -> None:
    run = _run_with_stages("plan", "implement", "review")
    defn = _definition_with_edges()
    graph = GraphBuilder(run, definition=defn).build()
    exec_edges = [e for e in graph.edges if e.edge_type == EdgeType.EXECUTION]
    assert len(exec_edges) == 2


def test_definition_entry_point_trigger_edge() -> None:
    run = _run_with_stages("plan", "implement")
    defn = _definition_with_edges()
    graph = GraphBuilder(run, definition=defn).build()
    trigger_edges = [e for e in graph.edges if e.edge_type == EdgeType.TRIGGER]
    assert len(trigger_edges) == 1
    assert trigger_edges[0].target_id == "stage-plan"


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


def test_empty_stages() -> None:
    run = PipelineRun(
        run_id="run-0",
        project_id="p",
        work_item_id="w",
        workflow_definition_id="d",
    )
    graph = GraphBuilder(run).build()
    assert len(graph.nodes) == 1  # trigger only
    assert graph.nodes[0].node_type == NodeType.TRIGGER


def test_manual_trigger_name() -> None:
    run = PipelineRun(
        run_id="run-0",
        project_id="p",
        work_item_id="w",
        workflow_definition_id="d",
        trigger_type="",
    )
    graph = GraphBuilder(run).build()
    assert graph.nodes[0].name == "manual"


def test_graph_is_frozen() -> None:
    run = _run_with_stages("plan")
    graph = GraphBuilder(run).build()
    try:
        graph.nodes = ()  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised
