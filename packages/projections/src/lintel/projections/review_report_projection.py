"""Review report projection — updates read model from ReviewCompleted events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class ReviewReportProjection:
    """Tracks the latest review report per repository."""

    HANDLED_TYPES: frozenset[str] = frozenset({"ReviewCompleted"})

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "review_report"

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        payload = event.payload
        repo_id = str(payload.get("repo_id", ""))
        report_id = str(payload.get("report_id", ""))
        pipeline_run_id = str(payload.get("pipeline_run_id", ""))

        self._state[repo_id] = {
            "repo_id": repo_id,
            "latest_report_id": report_id,
            "pipeline_run_id": pipeline_run_id,
            "completed_at": event.occurred_at.isoformat(),
            "review_count": self._state.get(repo_id, {}).get("review_count", 0) + 1,
        }

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._state.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_latest_report(self, repo_id: str) -> dict[str, Any] | None:
        return self._state.get(repo_id)

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._state.values())
