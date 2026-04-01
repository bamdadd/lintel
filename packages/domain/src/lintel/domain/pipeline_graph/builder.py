"""GraphBuilder — converts a PipelineRun into a PipelineGraph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.domain.pipeline_graph.models import (
    EdgeType,
    NodePosition,
    NodeType,
    PipelineEdge,
    PipelineGraph,
    PipelineNode,
)

if TYPE_CHECKING:
    from lintel.workflows.types import PipelineRun, WorkflowDefinitionRecord

_Y_SPACING = 120.0
_X_CENTER = 300.0


class GraphBuilder:
    """Builds a :class:`PipelineGraph` from a :class:`PipelineRun`.

    Optionally accepts a :class:`WorkflowDefinitionRecord` to enrich the
    graph with custom edge topology from the workflow definition.
    """

    def __init__(
        self,
        run: PipelineRun,
        definition: WorkflowDefinitionRecord | None = None,
    ) -> None:
        self._run = run
        self._definition = definition

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> PipelineGraph:
        """Return the fully-constructed pipeline graph."""
        nodes: list[PipelineNode] = []
        edges: list[PipelineEdge] = []

        y = 0.0

        # 1. Trigger node
        trigger_node = self._build_trigger_node(y)
        nodes.append(trigger_node)
        y += _Y_SPACING

        # 2. Stage nodes (linear chain from PipelineRun.stages)
        prev_id = trigger_node.node_id
        stage_node_ids: list[str] = []

        edges_from_def = self._edges_from_definition() if self._definition is not None else None

        for idx, stage in enumerate(self._run.stages):
            node_id = f"stage-{stage.stage_id}"
            node = PipelineNode(
                node_id=node_id,
                name=stage.name,
                node_type=NodeType.STAGE,
                position=NodePosition(x=_X_CENTER, y=y),
                metadata={
                    "stage_id": stage.stage_id,
                    "stage_type": stage.stage_type,
                    "status": str(stage.status),
                },
            )
            nodes.append(node)
            stage_node_ids.append(node_id)
            y += _Y_SPACING

            # Edge from trigger to first stage, or between stages
            if edges_from_def is None:
                if idx == 0:
                    edges.append(
                        PipelineEdge(
                            source_id=trigger_node.node_id,
                            target_id=node_id,
                            edge_type=EdgeType.TRIGGER,
                            label="triggers",
                        )
                    )
                else:
                    edges.append(
                        PipelineEdge(
                            source_id=prev_id,
                            target_id=node_id,
                            edge_type=EdgeType.EXECUTION,
                        )
                    )
                prev_id = node_id

        # If definition edges exist, apply them instead of the linear chain
        if edges_from_def is not None:
            # Trigger → entry point
            entry = self._definition.entry_point if self._definition else ""  # type: ignore[union-attr]
            entry_node_id = self._stage_name_to_node_id(entry, stage_node_ids)
            if entry_node_id:
                edges.append(
                    PipelineEdge(
                        source_id=trigger_node.node_id,
                        target_id=entry_node_id,
                        edge_type=EdgeType.TRIGGER,
                        label="triggers",
                    )
                )
            for src, tgt in edges_from_def:
                src_nid = self._stage_name_to_node_id(src, stage_node_ids)
                tgt_nid = self._stage_name_to_node_id(tgt, stage_node_ids)
                if src_nid and tgt_nid:
                    edges.append(
                        PipelineEdge(
                            source_id=src_nid,
                            target_id=tgt_nid,
                            edge_type=EdgeType.EXECUTION,
                        )
                    )

        # 3. Artifact nodes — one per stage that has outputs
        for stage in self._run.stages:
            if not stage.outputs:
                continue
            stage_nid = f"stage-{stage.stage_id}"
            artifact_nid = f"artifact-{stage.stage_id}"
            artifact_node = PipelineNode(
                node_id=artifact_nid,
                name=f"{stage.name} output",
                node_type=NodeType.ARTIFACT,
                position=NodePosition(x=_X_CENTER + 250.0, y=y),
                metadata={"source_stage": stage.stage_id},
            )
            nodes.append(artifact_node)
            edges.append(
                PipelineEdge(
                    source_id=stage_nid,
                    target_id=artifact_nid,
                    edge_type=EdgeType.DATA_FLOW,
                    label="produces",
                )
            )
            y += _Y_SPACING

        return PipelineGraph(nodes=tuple(nodes), edges=tuple(edges))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_trigger_node(self, y: float) -> PipelineNode:
        return PipelineNode(
            node_id=f"trigger-{self._run.run_id}",
            name=self._run.trigger_type or "manual",
            node_type=NodeType.TRIGGER,
            position=NodePosition(x=_X_CENTER, y=y),
            metadata={
                "trigger_type": self._run.trigger_type,
                "trigger_id": self._run.trigger_id,
            },
        )

    def _edges_from_definition(self) -> list[tuple[str, str]] | None:
        if self._definition is None or not self._definition.graph_edges:
            return None
        return list(self._definition.graph_edges)

    def _stage_name_to_node_id(self, name: str, stage_node_ids: list[str]) -> str | None:
        """Map a stage/node name to its graph node_id."""
        for stage in self._run.stages:
            if stage.name == name or stage.stage_id == name:
                nid = f"stage-{stage.stage_id}"
                if nid in stage_node_ids:
                    return nid
        return None
