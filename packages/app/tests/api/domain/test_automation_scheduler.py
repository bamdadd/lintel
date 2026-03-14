"""Tests for AutomationScheduler."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from lintel.api.domain.automation_scheduler import AutomationScheduler
from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import (
    AutomationDefinition,
    AutomationTriggerType,
    ConcurrencyPolicy,
)


def _cron_automation(
    automation_id: str = "a-1",
    schedule: str = "* * * * *",
    enabled: bool = True,
    concurrency: ConcurrencyPolicy = ConcurrencyPolicy.ALLOW,
) -> AutomationDefinition:
    return AutomationDefinition(
        automation_id=automation_id,
        name="Test",
        project_id="proj-1",
        workflow_definition_id="wf-1",
        trigger_type=AutomationTriggerType.CRON,
        trigger_config={"schedule": schedule, "timezone": "UTC"},
        concurrency_policy=concurrency,
        enabled=enabled,
    )


def _event_automation(
    automation_id: str = "a-evt",
    event_types: list[str] | None = None,
    max_chain_depth: int = 3,
) -> AutomationDefinition:
    return AutomationDefinition(
        automation_id=automation_id,
        name="On Complete",
        project_id="proj-1",
        workflow_definition_id="wf-1",
        trigger_type=AutomationTriggerType.EVENT,
        trigger_config={"event_types": event_types or ["PipelineRunCompleted"]},
        max_chain_depth=max_chain_depth,
    )


_CORR_ID = UUID("00000000-0000-0000-0000-000000000001")


class TestCronEvaluation:
    async def test_fires_when_due(self) -> None:
        store = AsyncMock()
        store.list_all.return_value = [_cron_automation()]
        fire_fn = AsyncMock(return_value="run-1")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        await scheduler.tick_cron()
        fire_fn.assert_called_once()

    async def test_skips_disabled(self) -> None:
        store = AsyncMock()
        store.list_all.return_value = [_cron_automation(enabled=False)]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        await scheduler.tick_cron()
        fire_fn.assert_not_called()

    async def test_no_double_fire(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(schedule="0 2 * * *")
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._last_fired["a-1"] = datetime.now(UTC)
        await scheduler.tick_cron()
        fire_fn.assert_not_called()


class TestConcurrencyPolicies:
    async def test_skip_policy_skips_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.SKIP)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        skip_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store,
            fire_fn=fire_fn,
            skip_fn=skip_fn,
        )
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_not_called()
        skip_fn.assert_called_once()

    async def test_allow_policy_fires_even_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.ALLOW)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock(return_value="run-new")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_called_once()

    async def test_queue_policy_enqueues_when_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.QUEUE)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        fire_fn.assert_not_called()
        assert len(scheduler._queues["a-1"]) == 1

    async def test_cancel_policy_cancels_active(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.CANCEL)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock(return_value="run-new")
        cancel_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store,
            fire_fn=fire_fn,
            cancel_fn=cancel_fn,
        )
        scheduler._active_runs["a-1"] = "run-123"
        await scheduler.tick_cron()
        cancel_fn.assert_called_once_with("a-1", "run-123")
        fire_fn.assert_called_once()

    async def test_queue_dequeues_on_completion(self) -> None:
        store = AsyncMock()
        auto = _cron_automation(concurrency=ConcurrencyPolicy.QUEUE)
        store.get.return_value = auto
        fire_fn = AsyncMock(return_value="run-next")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)
        scheduler._active_runs["a-1"] = "run-123"
        scheduler._queues["a-1"].append({"trigger": "cron"})
        await scheduler.mark_run_completed("a-1", "run-123")
        fire_fn.assert_called_once()
        assert scheduler._active_runs["a-1"] == "run-next"
        assert len(scheduler._queues["a-1"]) == 0


class TestEventTriggers:
    async def test_fires_on_matching_event(self) -> None:
        store = AsyncMock()
        auto = _event_automation()
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock(return_value="run-1")
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)

        event = EventEnvelope(
            event_type="PipelineRunCompleted",
            payload={"resource_id": "some-run"},
        )
        await scheduler.handle_event(event)
        fire_fn.assert_called_once()

    async def test_ignores_non_matching_event(self) -> None:
        store = AsyncMock()
        auto = _event_automation()
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        scheduler = AutomationScheduler(automation_store=store, fire_fn=fire_fn)

        event = EventEnvelope(
            event_type="WorkItemCreated",
            payload={"resource_id": "wi-1"},
        )
        await scheduler.handle_event(event)
        fire_fn.assert_not_called()

    async def test_chain_depth_exceeded_skips(self) -> None:
        store = AsyncMock()
        auto = _event_automation(max_chain_depth=2)
        store.list_all.return_value = [auto]
        fire_fn = AsyncMock()
        skip_fn = AsyncMock()
        scheduler = AutomationScheduler(
            automation_store=store,
            fire_fn=fire_fn,
            skip_fn=skip_fn,
        )
        scheduler._chain_depths[_CORR_ID] = 3
        event = EventEnvelope(
            event_type="PipelineRunCompleted",
            payload={"resource_id": "r-1"},
            correlation_id=_CORR_ID,
        )
        await scheduler.handle_event(event)
        fire_fn.assert_not_called()
        skip_fn.assert_called_once()
