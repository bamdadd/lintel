"""Memory consolidation projection.

Reacts to ``PipelineRunCompleted`` events and stores episodic memories
via :class:`~lintel.memory.MemoryService`.  Near-duplicate summaries are
deduplicated automatically by the memory service (cosine > 0.95 → update).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.memory import MemoryService

logger = structlog.get_logger()


class MemoryConsolidationProjection:
    """Consolidates workflow summaries into episodic memory on completion."""

    HANDLED_TYPES: frozenset[str] = frozenset({"PipelineRunCompleted"})

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory_service = memory_service
        self._state: dict[str, Any] = {"consolidated_count": 0, "last_workflow_id": None}

    # -- Projection protocol --------------------------------------------------

    @property
    def name(self) -> str:
        return "memory_consolidation"

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        if event.event_type != "PipelineRunCompleted":
            return

        payload = event.payload
        workflow_id_raw = payload.get("workflow_id") or payload.get("run_id")
        project_id_raw = payload.get("project_id")
        summary_text = payload.get("summary") or payload.get("result", "")

        if not workflow_id_raw or not project_id_raw:
            logger.warning(
                "memory_consolidation_skipped",
                reason="missing workflow_id or project_id",
                event_id=str(event.event_id),
            )
            return

        if not summary_text:
            logger.debug(
                "memory_consolidation_skipped",
                reason="empty summary",
                workflow_id=str(workflow_id_raw),
            )
            return

        workflow_id = UUID(str(workflow_id_raw))
        project_id = UUID(str(project_id_raw))

        try:
            facts = await self._memory_service.consolidate_from_workflow(
                workflow_id=workflow_id,
                project_id=project_id,
                summary_text=summary_text,
            )
            self._state["consolidated_count"] = self._state.get("consolidated_count", 0) + 1
            self._state["last_workflow_id"] = str(workflow_id)
            logger.info(
                "memory_consolidation_projected",
                workflow_id=str(workflow_id),
                project_id=str(project_id),
                facts_count=len(facts),
            )
        except Exception:
            logger.exception(
                "memory_consolidation_failed",
                workflow_id=str(workflow_id_raw),
                project_id=str(project_id_raw),
            )

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._state = {"consolidated_count": 0, "last_workflow_id": None}
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)
