"""Task backlog projection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class TaskBacklogProjection:
    """Maintains an in-memory task backlog view from agent events."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "AgentStepScheduled",
            "AgentStepStarted",
            "AgentStepCompleted",
        }
    )

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        task_key = f"{event.correlation_id}"
        current = self._tasks.get(
            task_key,
            {
                "correlation_id": str(event.correlation_id),
                "thread_ref": str(event.thread_ref) if event.thread_ref else "unknown",
            },
        )

        status_map = {
            "AgentStepScheduled": "scheduled",
            "AgentStepStarted": "in_progress",
            "AgentStepCompleted": "completed",
        }
        current["status"] = status_map.get(event.event_type, current.get("status", "unknown"))
        current["last_event_at"] = event.occurred_at.isoformat()
        current.update({k: v for k, v in event.payload.items() if k in ("agent_role", "step_name")})

        self._tasks[task_key] = current

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._tasks.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_backlog(self) -> list[dict[str, Any]]:
        return list(self._tasks.values())

    def get_pending(self) -> list[dict[str, Any]]:
        return [t for t in self._tasks.values() if t.get("status") != "completed"]
