"""Tests for the Workflow Hook Manager."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from lintel.automations_api.hooks.hook_manager import (
    HookManager,
    _conditions_match,
    _pattern_matches,
    _resolve_params,
)
from lintel.contracts.events import EventEnvelope
from lintel.domain.events import HookLoopDetected, HookTriggered
from lintel.domain.types import HookType, WorkflowHook


def _make_event(event_type: str, payload: dict[str, Any] | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        payload=payload or {},
        correlation_id=uuid4(),
    )


def _make_hook(
    event_pattern: str = "PipelineRunCompleted",
    workflow_id: str = "wf-1",
    conditions: dict[str, object] | None = None,
    params_template: dict[str, str] | None = None,
    max_chain_depth: int = 5,
) -> WorkflowHook:
    return WorkflowHook(
        hook_id=str(uuid4()),
        project_id="p1",
        name="test-hook",
        event_pattern=event_pattern,
        hook_type=HookType.POST,
        workflow_id=workflow_id,
        conditions=conditions,
        params_template=params_template,
        max_chain_depth=max_chain_depth,
    )


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)

    async def subscribe(self, event_types: frozenset[str], handler: object) -> str:
        return "sub-1"

    async def unsubscribe(self, subscription_id: str) -> None:
        pass


class TestPatternMatching:
    def test_exact_match(self) -> None:
        assert _pattern_matches("PipelineRunCompleted", "PipelineRunCompleted")

    def test_wildcard_all(self) -> None:
        assert _pattern_matches("*", "anything")

    def test_empty_matches_all(self) -> None:
        assert _pattern_matches("", "anything")

    def test_glob_prefix(self) -> None:
        assert _pattern_matches("Pipeline*", "PipelineRunCompleted")
        assert not _pattern_matches("Pipeline*", "WorkItemCreated")

    def test_glob_suffix(self) -> None:
        assert _pattern_matches("*Completed", "PipelineRunCompleted")
        assert _pattern_matches("*Completed", "DeliveryLoopCompleted")
        assert not _pattern_matches("*Completed", "PipelineRunStarted")

    def test_no_match(self) -> None:
        assert not _pattern_matches("WorkItemCreated", "PipelineRunCompleted")


class TestConditionsMatch:
    def test_empty_conditions(self) -> None:
        assert _conditions_match({}, {"any": "thing"})

    def test_matching(self) -> None:
        assert _conditions_match({"stage": "review"}, {"stage": "review", "status": "ok"})

    def test_not_matching(self) -> None:
        assert not _conditions_match({"stage": "review"}, {"stage": "deploy"})

    def test_missing_key(self) -> None:
        assert not _conditions_match({"stage": "review"}, {})


class TestResolveParams:
    def test_none_template(self) -> None:
        assert _resolve_params(None, {"x": 1}) == {}

    def test_literal_values(self) -> None:
        assert _resolve_params({"key": "literal"}, {}) == {"key": "literal"}

    def test_template_substitution(self) -> None:
        result = _resolve_params(
            {"commit": "{{ event.sha }}", "branch": "{{ event.ref }}"},
            {"sha": "abc123", "ref": "main"},
        )
        assert result == {"commit": "abc123", "branch": "main"}

    def test_missing_field_returns_empty(self) -> None:
        result = _resolve_params({"x": "{{ event.missing }}"}, {})
        assert result == {"x": ""}


class TestHookTriggering:
    async def test_matching_hook_fires(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(_make_hook(event_pattern="PipelineRunCompleted"))

        await mgr.handle(_make_event("PipelineRunCompleted"))

        triggered = [e for e in bus.published if isinstance(e, HookTriggered)]
        assert len(triggered) == 1
        assert mgr.stats["triggered"] == 1

    async def test_non_matching_hook_skipped(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(_make_hook(event_pattern="WorkItemCreated"))

        await mgr.handle(_make_event("PipelineRunCompleted"))

        assert len(bus.published) == 0
        assert mgr.stats["triggered"] == 0

    async def test_disabled_hook_skipped(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        hook = WorkflowHook(
            hook_id="h1",
            project_id="p1",
            name="disabled",
            event_pattern="*",
            enabled=False,
        )
        mgr.register(hook)

        await mgr.handle(_make_event("PipelineRunCompleted"))
        assert mgr.stats["triggered"] == 0

    async def test_conditions_filter(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(
            _make_hook(
                event_pattern="PipelineStageCompleted",
                conditions={"stage": "review"},
            )
        )

        await mgr.handle(_make_event("PipelineStageCompleted", {"stage": "deploy"}))
        assert mgr.stats["triggered"] == 0

        await mgr.handle(_make_event("PipelineStageCompleted", {"stage": "review"}))
        assert mgr.stats["triggered"] == 1

    async def test_on_trigger_callback(self) -> None:
        triggered: list[tuple[str, str]] = []

        async def callback(
            hook: WorkflowHook,
            event: EventEnvelope,
            params: dict[str, Any],
        ) -> None:
            triggered.append((hook.hook_id, event.event_type))

        mgr = HookManager(on_trigger=callback)
        hook = _make_hook(event_pattern="*")
        mgr.register(hook)

        await mgr.handle(_make_event("SomeEvent"))
        assert len(triggered) == 1
        assert triggered[0][1] == "SomeEvent"


class TestChainDepthProtection:
    async def test_loop_blocked(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(_make_hook(event_pattern="*", max_chain_depth=2))

        # Chain depth 2 should be blocked
        event = _make_event("SomeEvent", {"__hook_chain_depth": 2})
        await mgr.handle(event)

        assert mgr.stats["triggered"] == 0
        assert mgr.stats["blocked_loops"] == 1
        loop_events = [e for e in bus.published if isinstance(e, HookLoopDetected)]
        assert len(loop_events) == 1

    async def test_within_depth_allowed(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(_make_hook(event_pattern="*", max_chain_depth=5))

        event = _make_event("SomeEvent", {"__hook_chain_depth": 3})
        await mgr.handle(event)

        assert mgr.stats["triggered"] == 1

    async def test_skips_own_events(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        mgr.register(_make_hook(event_pattern="*"))

        await mgr.handle(_make_event("HookTriggered"))
        await mgr.handle(_make_event("HookExecutionFailed"))
        await mgr.handle(_make_event("HookLoopDetected"))

        assert mgr.stats["triggered"] == 0


class TestStartStop:
    async def test_start_subscribes(self) -> None:
        bus = FakeEventBus()
        mgr = HookManager(event_bus=bus)
        await mgr.start()
        assert mgr._subscription_id == "sub-1"

    async def test_register_unregister(self) -> None:
        mgr = HookManager()
        hook = _make_hook()
        mgr.register(hook)
        assert mgr.stats["hooks_registered"] == 1
        mgr.unregister(hook.hook_id)
        assert mgr.stats["hooks_registered"] == 0
