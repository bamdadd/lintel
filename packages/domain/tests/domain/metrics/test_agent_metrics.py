"""Tests for agent metrics: dataclass, collector, and projection."""

from __future__ import annotations

from uuid import uuid4

import pytest

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.domain.metrics.agent_metrics import (
    AgentMetrics,
    AgentMetricsCollector,
    AgentMetricsProjection,
    _is_status_regression,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type: str,
    payload: dict | None = None,
    event_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4() if event_id is None else event_id,  # type: ignore[arg-type]
        event_type=event_type,
        actor_type=ActorType.SYSTEM,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# AgentMetrics dataclass
# ---------------------------------------------------------------------------


class TestAgentMetrics:
    def test_defaults(self) -> None:
        m = AgentMetrics(agent_role="coder")
        assert m.accuracy_score == 1.0
        assert m.rework_rate == 0.0
        assert m.token_efficiency == 0.0
        assert m.avg_step_duration_ms == 0.0

    def test_accuracy_score(self) -> None:
        m = AgentMetrics(agent_role="coder", tasks_completed=10, rework_count=2)
        assert m.accuracy_score == pytest.approx(0.8)

    def test_accuracy_score_clamps_to_zero(self) -> None:
        m = AgentMetrics(agent_role="coder", tasks_completed=2, rework_count=5)
        assert m.accuracy_score == 0.0

    def test_rework_rate(self) -> None:
        m = AgentMetrics(agent_role="coder", tasks_completed=10, rework_count=3)
        assert m.rework_rate == pytest.approx(0.3)

    def test_token_efficiency(self) -> None:
        m = AgentMetrics(
            agent_role="coder",
            tasks_completed=5,
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        assert m.token_efficiency == pytest.approx(300.0)

    def test_avg_step_duration(self) -> None:
        m = AgentMetrics(agent_role="coder", total_duration_ms=3000, step_count=3)
        assert m.avg_step_duration_ms == pytest.approx(1000.0)

    def test_to_dict_keys(self) -> None:
        m = AgentMetrics(agent_role="coder")
        d = m.to_dict()
        expected_keys = {
            "agent_role",
            "tasks_completed",
            "rework_count",
            "accuracy_score",
            "rework_rate",
            "total_input_tokens",
            "total_output_tokens",
            "token_efficiency",
            "total_cost_usd",
            "total_duration_ms",
            "step_count",
            "avg_step_duration_ms",
        }
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# AgentMetricsCollector
# ---------------------------------------------------------------------------


class TestAgentMetricsCollector:
    def test_apply_step_completed(self) -> None:
        m = AgentMetrics(agent_role="coder")
        AgentMetricsCollector.apply_step_completed(m, {"step_name": "implement"})
        assert m.tasks_completed == 1

    def test_apply_model_call(self) -> None:
        m = AgentMetrics(agent_role="coder")
        AgentMetricsCollector.apply_model_call(
            m,
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.005,
                "duration_ms": 1200,
            },
        )
        assert m.total_input_tokens == 100
        assert m.total_output_tokens == 50
        assert m.total_cost_usd == pytest.approx(0.005)
        assert m.total_duration_ms == 1200
        assert m.step_count == 1

    def test_apply_rework(self) -> None:
        m = AgentMetrics(agent_role="coder")
        AgentMetricsCollector.apply_rework(m)
        assert m.rework_count == 1


# ---------------------------------------------------------------------------
# Status regression helper
# ---------------------------------------------------------------------------


class TestStatusRegression:
    def test_regression_detected(self) -> None:
        assert _is_status_regression("in_review", "in_progress") is True

    def test_forward_not_regression(self) -> None:
        assert _is_status_regression("todo", "in_progress") is False

    def test_same_not_regression(self) -> None:
        assert _is_status_regression("done", "done") is False

    def test_unknown_status(self) -> None:
        assert _is_status_regression("custom", "todo") is False


# ---------------------------------------------------------------------------
# AgentMetricsProjection
# ---------------------------------------------------------------------------


class TestAgentMetricsProjection:
    async def test_handles_agent_step_completed(self) -> None:
        proj = AgentMetricsProjection()
        event = _make_event(
            "AgentStepCompleted",
            {"agent_role": "coder", "step_name": "implement"},
        )
        await proj.project(event)
        m = proj.get_metrics("coder")
        assert m is not None
        assert m.tasks_completed == 1

    async def test_handles_model_call_completed(self) -> None:
        proj = AgentMetricsProjection()
        event = _make_event(
            "ModelCallCompleted",
            {
                "agent_role": "reviewer",
                "input_tokens": 200,
                "output_tokens": 100,
                "cost_usd": 0.01,
                "duration_ms": 500,
            },
        )
        await proj.project(event)
        m = proj.get_metrics("reviewer")
        assert m is not None
        assert m.total_input_tokens == 200
        assert m.total_cost_usd == pytest.approx(0.01)

    async def test_handles_human_approval_rejected(self) -> None:
        proj = AgentMetricsProjection()
        event = _make_event("HumanApprovalRejected", {"agent_role": "coder"})
        await proj.project(event)
        m = proj.get_metrics("coder")
        assert m is not None
        assert m.rework_count == 1

    async def test_handles_work_item_status_regression(self) -> None:
        proj = AgentMetricsProjection()
        event = _make_event(
            "WorkItemUpdated",
            {"agent_role": "coder", "old_status": "in_review", "status": "in_progress"},
        )
        await proj.project(event)
        m = proj.get_metrics("coder")
        assert m is not None
        assert m.rework_count == 1

    async def test_ignores_work_item_forward_transition(self) -> None:
        proj = AgentMetricsProjection()
        event = _make_event(
            "WorkItemUpdated",
            {"agent_role": "coder", "old_status": "todo", "status": "in_progress"},
        )
        await proj.project(event)
        m = proj.get_metrics("coder")
        assert m is None  # no rework recorded, no role entry created

    async def test_idempotent(self) -> None:
        proj = AgentMetricsProjection()
        eid = uuid4()
        event = _make_event(
            "AgentStepCompleted",
            {"agent_role": "coder"},
            event_id=eid,  # type: ignore[arg-type]
        )
        await proj.project(event)
        await proj.project(event)
        m = proj.get_metrics("coder")
        assert m is not None
        assert m.tasks_completed == 1

    async def test_rebuild(self) -> None:
        proj = AgentMetricsProjection()
        events = [
            _make_event("AgentStepCompleted", {"agent_role": "coder"}),
            _make_event(
                "ModelCallCompleted",
                {
                    "agent_role": "coder",
                    "input_tokens": 50,
                    "output_tokens": 25,
                    "cost_usd": 0.001,
                    "duration_ms": 100,
                },
            ),
            _make_event("HumanApprovalRejected", {"agent_role": "coder"}),
        ]
        await proj.rebuild(events)
        m = proj.get_metrics("coder")
        assert m is not None
        assert m.tasks_completed == 1
        assert m.rework_count == 1
        assert m.total_input_tokens == 50

    async def test_get_all_metrics(self) -> None:
        proj = AgentMetricsProjection()
        await proj.project(_make_event("AgentStepCompleted", {"agent_role": "coder"}))
        await proj.project(_make_event("AgentStepCompleted", {"agent_role": "reviewer"}))
        all_m = proj.get_all_metrics()
        assert len(all_m) == 2
        roles = {m.agent_role for m in all_m}
        assert roles == {"coder", "reviewer"}

    async def test_get_state_and_restore(self) -> None:
        proj = AgentMetricsProjection()
        await proj.project(_make_event("AgentStepCompleted", {"agent_role": "coder"}))
        await proj.project(
            _make_event(
                "ModelCallCompleted",
                {
                    "agent_role": "coder",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_usd": 0.01,
                    "duration_ms": 500,
                },
            ),
        )

        state = proj.get_state()
        assert "by_role" in state
        assert "coder" in state["by_role"]

        # Restore into a fresh projection
        proj2 = AgentMetricsProjection()
        proj2.restore_state(state)
        m = proj2.get_metrics("coder")
        assert m is not None
        assert m.tasks_completed == 1
        assert m.total_input_tokens == 100
        assert m.total_cost_usd == pytest.approx(0.01)

    async def test_handled_event_types(self) -> None:
        proj = AgentMetricsProjection()
        expected = {
            "AgentStepCompleted",
            "ModelCallCompleted",
            "HumanApprovalRejected",
            "WorkItemUpdated",
        }
        assert proj.handled_event_types == expected

    async def test_name(self) -> None:
        proj = AgentMetricsProjection()
        assert proj.name == "agent_metrics"

    async def test_accuracy_after_mixed_events(self) -> None:
        """End-to-end: 5 completions, 1 rework -> accuracy 0.8."""
        proj = AgentMetricsProjection()
        for _ in range(5):
            await proj.project(_make_event("AgentStepCompleted", {"agent_role": "coder"}))
        await proj.project(_make_event("HumanApprovalRejected", {"agent_role": "coder"}))

        m = proj.get_metrics("coder")
        assert m is not None
        assert m.accuracy_score == pytest.approx(0.8)
        assert m.rework_rate == pytest.approx(0.2)
