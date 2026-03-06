"""Thread status projection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class ThreadStatusProjection:
    """Maintains an in-memory thread status view."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "ThreadMessageReceived",
            "WorkflowStarted",
            "WorkflowAdvanced",
            "HumanApprovalGranted",
            "HumanApprovalRejected",
        }
    )

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        thread_key = str(event.thread_ref) if event.thread_ref else "unknown"
        current = self._state.get(
            thread_key,
            {
                "thread_ref": thread_key,
                "status": "new",
                "event_count": 0,
            },
        )
        current["last_event_type"] = event.event_type
        current["last_event_at"] = event.occurred_at.isoformat()
        current["event_count"] = current.get("event_count", 0) + 1

        status_map = {
            "WorkflowStarted": "active",
            "WorkflowAdvanced": "active",
            "HumanApprovalGranted": "approved",
            "HumanApprovalRejected": "rejected",
        }
        if event.event_type in status_map:
            current["status"] = status_map[event.event_type]

        self._state[thread_key] = current

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._state.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_status(self, thread_ref: str) -> dict[str, Any] | None:
        return self._state.get(thread_ref)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._state.values())
