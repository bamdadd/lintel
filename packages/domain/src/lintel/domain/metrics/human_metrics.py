"""Human metrics: review time, approval latency, contributions (MET-3).

Aggregates data from approval and review events to produce human-interaction
metrics for dashboards and experimentation KPIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


@dataclass(frozen=True)
class HumanMetrics:
    """Snapshot of human-interaction metrics."""

    avg_review_time_seconds: float = 0.0
    avg_approval_latency_seconds: float = 0.0
    total_contributions: int = 0
    contribution_types: dict[str, int] = field(default_factory=dict)


class HumanMetricsCollector:
    """Collects human-interaction metrics from domain events.

    Feed events via :meth:`handle` and read the current snapshot
    via :meth:`snapshot`.
    """

    def __init__(self) -> None:
        self._review_times: list[float] = []
        self._approval_latencies: list[float] = []
        self._total_contributions: int = 0
        self._contribution_types: dict[str, int] = {}

    # -- public API ----------------------------------------------------------

    def handle(self, event: EventEnvelope) -> None:
        """Process a single domain event."""
        etype = event.event_type
        payload = event.payload

        if etype == "ApprovalRequested":
            # Nothing to record yet — we need the matching approved/rejected.
            pass
        elif etype in (
            "ApprovalRequestApproved",
            "ApprovalRequestRejected",
            "HumanApprovalGranted",
            "HumanApprovalRejected",
        ):
            self._record_approval_latency(payload)
            self._record_contribution(etype)
        elif etype == "ApprovalExpired":
            self._record_contribution(etype)
        else:
            # Generic contribution (e.g. review events added in the future).
            if payload.get("review_time_seconds") is not None:
                self._review_times.append(float(payload["review_time_seconds"]))
            if payload.get("contribution_type") is not None:
                self._record_contribution(str(payload["contribution_type"]))

    def snapshot(self) -> HumanMetrics:
        """Return a frozen snapshot of the current metrics."""
        avg_review = (
            sum(self._review_times) / len(self._review_times) if self._review_times else 0.0
        )
        avg_approval = (
            sum(self._approval_latencies) / len(self._approval_latencies)
            if self._approval_latencies
            else 0.0
        )
        return HumanMetrics(
            avg_review_time_seconds=avg_review,
            avg_approval_latency_seconds=avg_approval,
            total_contributions=self._total_contributions,
            contribution_types=dict(self._contribution_types),
        )

    def reset(self) -> None:
        """Clear all collected data."""
        self._review_times.clear()
        self._approval_latencies.clear()
        self._total_contributions = 0
        self._contribution_types.clear()

    # -- internals -----------------------------------------------------------

    def _record_approval_latency(self, payload: dict[str, object]) -> None:
        latency = payload.get("approval_latency_seconds")
        if latency is not None:
            self._approval_latencies.append(float(str(latency)))

    def _record_contribution(self, contribution_type: str) -> None:
        self._total_contributions += 1
        self._contribution_types[contribution_type] = (
            self._contribution_types.get(contribution_type, 0) + 1
        )
