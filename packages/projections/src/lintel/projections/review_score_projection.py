"""Review score projection — builds read model from ReviewScoreRecorded events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class ReviewScoreProjection:
    """Maintains an in-memory view of review scores per repo and dimension."""

    HANDLED_TYPES: frozenset[str] = frozenset({"ReviewScoreRecorded"})

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "review_score"

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
        dimension = str(payload.get("dimension", ""))
        score = float(payload.get("score", 0.0))
        score_id = str(payload.get("score_id", ""))

        key = f"{repo_id}:{dimension}"
        self._state[key] = {
            "repo_id": repo_id,
            "dimension": dimension,
            "latest_score": score,
            "score_id": score_id,
            "last_event_at": event.occurred_at.isoformat(),
            "event_count": self._state.get(key, {}).get("event_count", 0) + 1,
        }

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._state.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_latest_scores(self, repo_id: str) -> list[dict[str, Any]]:
        """Get the latest score per dimension for a repo."""
        return [v for v in self._state.values() if v.get("repo_id") == repo_id]

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._state.values())
