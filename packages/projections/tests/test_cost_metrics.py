"""Tests for CostMetricsProjection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from lintel.contracts.types import ActorType

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
from lintel.models.events import ModelCallCompleted
from lintel.projections.cost_metrics import CostMetricsProjection


def _make_event(
    *,
    model: str = "gpt-4",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: float = 0.005,
    duration_ms: int = 200,
    agent_role: str = "coder",
    run_id: str = "run-1",
    stage: str = "implement",
    project_id: str = "proj-1",
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    kwargs = {}
    if occurred_at is not None:
        kwargs["occurred_at"] = occurred_at
    return ModelCallCompleted(
        actor_type=ActorType.SYSTEM,
        actor_id="model_router",
        event_id=uuid4(),
        payload={
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "agent_role": agent_role,
            "run_id": run_id,
            "stage": stage,
            "project_id": project_id,
        },
        **kwargs,
    )


class TestCostMetricsProjection:
    async def test_handles_model_call_completed(self) -> None:
        proj = CostMetricsProjection()
        assert "ModelCallCompleted" in proj.handled_event_types

    async def test_project_single_event(self) -> None:
        proj = CostMetricsProjection()
        event = _make_event()
        await proj.project(event)

        run_data = proj.get_costs_by_run("run-1")
        assert run_data["total_cost_usd"] == 0.005
        assert run_data["total_input_tokens"] == 100
        assert run_data["total_output_tokens"] == 50
        assert run_data["call_count"] == 1

    async def test_aggregation_across_multiple_events(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(cost_usd=0.01, input_tokens=100, output_tokens=50))
        await proj.project(_make_event(cost_usd=0.02, input_tokens=200, output_tokens=100))

        run_data = proj.get_costs_by_run("run-1")
        assert run_data["call_count"] == 2
        assert run_data["total_input_tokens"] == 300
        assert run_data["total_output_tokens"] == 150
        assert abs(run_data["total_cost_usd"] - 0.03) < 1e-6

    async def test_per_stage_breakdown(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(stage="research", cost_usd=0.01))
        await proj.project(_make_event(stage="implement", cost_usd=0.02))
        await proj.project(_make_event(stage="implement", cost_usd=0.03))

        stages = proj.get_costs_by_stage("run-1")
        assert len(stages) == 2
        stage_map = {s["stage"]: s for s in stages}
        assert stage_map["research"]["call_count"] == 1
        assert stage_map["implement"]["call_count"] == 2
        assert abs(stage_map["implement"]["total_cost_usd"] - 0.05) < 1e-6

    async def test_per_project_daily(self) -> None:
        proj = CostMetricsProjection()
        today = datetime.now(UTC)
        yesterday = today - timedelta(days=1)
        await proj.project(_make_event(occurred_at=today, cost_usd=0.01))
        await proj.project(_make_event(occurred_at=yesterday, cost_usd=0.02))

        result = proj.get_costs_by_project("proj-1")
        assert result["call_count"] == 2
        assert len(result["time_series"]) == 2

    async def test_per_agent_role(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(agent_role="coder", cost_usd=0.01))
        await proj.project(_make_event(agent_role="reviewer", cost_usd=0.005))

        roles = proj.get_costs_by_agent_role(project_id="proj-1")
        assert len(roles) == 2
        role_map = {r["agent_role"]: r for r in roles}
        assert role_map["coder"]["call_count"] == 1
        assert role_map["reviewer"]["call_count"] == 1

    async def test_idempotency_duplicate_event_id(self) -> None:
        proj = CostMetricsProjection()
        event = _make_event(cost_usd=0.01)
        await proj.project(event)
        await proj.project(event)  # same event_id

        run_data = proj.get_costs_by_run("run-1")
        assert run_data["call_count"] == 1
        assert run_data["total_cost_usd"] == 0.01

    async def test_model_breakdown(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(model="gpt-4", cost_usd=0.01))
        await proj.project(_make_event(model="claude-3-sonnet", cost_usd=0.005))

        result = proj.get_costs_by_project("proj-1")
        models = result["breakdown_by_model"]
        assert len(models) == 2
        model_map = {m["model"]: m for m in models}
        assert model_map["gpt-4"]["call_count"] == 1
        assert model_map["claude-3-sonnet"]["call_count"] == 1

    async def test_weekly_aggregation(self) -> None:
        proj = CostMetricsProjection()
        today = datetime.now(UTC)
        for i in range(7):
            await proj.project(
                _make_event(
                    occurred_at=today - timedelta(days=i),
                    cost_usd=0.01,
                )
            )

        result = proj.get_costs_by_project("proj-1", period="weekly")
        # All 7 days should collapse into 1-2 weeks
        assert len(result["time_series"]) <= 2

    async def test_date_filtering(self) -> None:
        proj = CostMetricsProjection()
        today = datetime.now(UTC)
        old = today - timedelta(days=30)
        await proj.project(_make_event(occurred_at=today, cost_usd=0.01))
        await proj.project(_make_event(occurred_at=old, cost_usd=0.02))

        result = proj.get_costs_by_project(
            "proj-1",
            start_date=(today - timedelta(days=1)).date().isoformat(),
        )
        assert result["call_count"] == 1
        assert result["total_cost_usd"] == 0.01

    async def test_empty_run_returns_zeroes(self) -> None:
        proj = CostMetricsProjection()
        data = proj.get_costs_by_run("nonexistent")
        assert data["call_count"] == 0
        assert data["total_cost_usd"] == 0.0

    async def test_rebuild_clears_and_replays(self) -> None:
        proj = CostMetricsProjection()
        e1 = _make_event(cost_usd=0.01)
        e2 = _make_event(cost_usd=0.02)
        await proj.project(e1)
        await proj.project(e2)
        assert proj.get_costs_by_run("run-1")["call_count"] == 2

        # Rebuild with only one event
        await proj.rebuild([e1])
        assert proj.get_costs_by_run("run-1")["call_count"] == 1

    async def test_state_serialization_roundtrip(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(cost_usd=0.01))
        await proj.project(_make_event(cost_usd=0.02, model="claude-3"))

        state = proj.get_state()

        proj2 = CostMetricsProjection()
        proj2.restore_state(state)

        assert proj2.get_costs_by_run("run-1")["call_count"] == 2
        assert abs(proj2.get_costs_by_run("run-1")["total_cost_usd"] - 0.03) < 1e-6

    async def test_raw_events_query(self) -> None:
        proj = CostMetricsProjection()
        await proj.project(_make_event(run_id="run-1", cost_usd=0.01))
        await proj.project(_make_event(run_id="run-2", cost_usd=0.02))

        all_events = proj.get_all_raw_events()
        assert len(all_events) == 2

        run1_events = proj.get_all_raw_events(run_id="run-1")
        assert len(run1_events) == 1
        assert run1_events[0]["run_id"] == "run-1"

    async def test_projection_name(self) -> None:
        proj = CostMetricsProjection()
        assert proj.name == "cost_metrics"
