"""Tests for HumanMetrics and HumanMetricsCollector (MET-3)."""

from __future__ import annotations

from lintel.contracts.events import EventEnvelope
from lintel.domain.metrics.human_metrics import HumanMetrics, HumanMetricsCollector


def _event(event_type: str, payload: dict | None = None) -> EventEnvelope:
    return EventEnvelope(event_type=event_type, payload=payload or {})


class TestHumanMetrics:
    def test_defaults(self) -> None:
        m = HumanMetrics()
        assert m.avg_review_time_seconds == 0.0
        assert m.avg_approval_latency_seconds == 0.0
        assert m.total_contributions == 0
        assert m.contribution_types == {}

    def test_frozen(self) -> None:
        m = HumanMetrics()
        try:
            m.avg_review_time_seconds = 1.0  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("Expected frozen dataclass")


class TestHumanMetricsCollector:
    def test_empty_snapshot(self) -> None:
        c = HumanMetricsCollector()
        snap = c.snapshot()
        assert snap == HumanMetrics()

    def test_approval_latency_from_approved(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequestApproved", {"approval_latency_seconds": 120}))
        c.handle(_event("ApprovalRequestApproved", {"approval_latency_seconds": 60}))
        snap = c.snapshot()
        assert snap.avg_approval_latency_seconds == 90.0
        assert snap.total_contributions == 2
        assert snap.contribution_types["ApprovalRequestApproved"] == 2

    def test_approval_latency_from_rejected(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequestRejected", {"approval_latency_seconds": 30}))
        snap = c.snapshot()
        assert snap.avg_approval_latency_seconds == 30.0
        assert snap.total_contributions == 1

    def test_human_approval_granted(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("HumanApprovalGranted", {"approval_latency_seconds": 200}))
        snap = c.snapshot()
        assert snap.avg_approval_latency_seconds == 200.0
        assert snap.contribution_types["HumanApprovalGranted"] == 1

    def test_human_approval_rejected(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("HumanApprovalRejected", {"approval_latency_seconds": 50}))
        snap = c.snapshot()
        assert snap.avg_approval_latency_seconds == 50.0

    def test_approval_expired_counts_contribution(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalExpired"))
        snap = c.snapshot()
        assert snap.total_contributions == 1
        assert snap.contribution_types["ApprovalExpired"] == 1
        assert snap.avg_approval_latency_seconds == 0.0

    def test_review_time_via_payload(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("CodeReviewCompleted", {"review_time_seconds": 300}))
        c.handle(_event("CodeReviewCompleted", {"review_time_seconds": 100}))
        snap = c.snapshot()
        assert snap.avg_review_time_seconds == 200.0

    def test_contribution_type_via_payload(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("SomeEvent", {"contribution_type": "code_review"}))
        snap = c.snapshot()
        assert snap.contribution_types["code_review"] == 1
        assert snap.total_contributions == 1

    def test_approval_without_latency_still_counts(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequestApproved", {}))
        snap = c.snapshot()
        assert snap.total_contributions == 1
        assert snap.avg_approval_latency_seconds == 0.0

    def test_mixed_events(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequestApproved", {"approval_latency_seconds": 100}))
        c.handle(_event("HumanApprovalGranted", {"approval_latency_seconds": 200}))
        c.handle(_event("ApprovalExpired"))
        c.handle(
            _event(
                "CodeReviewCompleted",
                {"review_time_seconds": 60, "contribution_type": "code_review"},
            )
        )
        snap = c.snapshot()
        assert snap.avg_approval_latency_seconds == 150.0
        assert snap.avg_review_time_seconds == 60.0
        assert snap.total_contributions == 4

    def test_reset(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequestApproved", {"approval_latency_seconds": 100}))
        c.reset()
        snap = c.snapshot()
        assert snap == HumanMetrics()

    def test_approval_requested_is_noop(self) -> None:
        c = HumanMetricsCollector()
        c.handle(_event("ApprovalRequested"))
        snap = c.snapshot()
        assert snap == HumanMetrics()
