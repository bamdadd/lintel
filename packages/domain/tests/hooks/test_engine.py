"""Tests for the HookEngine — pre/post hook evaluation."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.domain.events import (
    HookLoopDetected,
    HookTriggered,
    PreHookAllowed,
    PreHookBlocked,
)
from lintel.domain.hooks.engine import HookEngine
from lintel.domain.types import (
    HookActionType,
    HookResult,
    HookType,
    PreHookDecision,
    WorkflowHook,
)


def _evt(event_type: str = "PipelineRunCompleted", **extra: object) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        payload=extra,
        correlation_id=uuid4(),
    )


def _hook(
    event_pattern: str = "PipelineRunCompleted",
    hook_type: HookType = HookType.POST,
    action_type: HookActionType = HookActionType.TRIGGER_WORKFLOW,
    workflow_id: str = "wf-1",
    webhook_url: str = "",
    conditions: dict[str, object] | None = None,
    params_template: dict[str, str] | None = None,
    max_chain_depth: int = 5,
) -> WorkflowHook:
    return WorkflowHook(
        hook_id=str(uuid4()),
        project_id="p1",
        name="test-hook",
        event_pattern=event_pattern,
        hook_type=hook_type,
        action_type=action_type,
        workflow_id=workflow_id,
        webhook_url=webhook_url,
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


# ---------------------------------------------------------------------------
# Post-hook tests
# ---------------------------------------------------------------------------


class TestPostHookFiring:
    async def test_matching_post_hook_fires(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook())

        await engine.handle(_evt())

        triggered = [e for e in bus.published if isinstance(e, HookTriggered)]
        assert len(triggered) == 1
        assert engine.stats["triggered"] == 1

    async def test_non_matching_skipped(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="WorkItemCreated"))

        await engine.handle(_evt())
        assert engine.stats["triggered"] == 0

    async def test_disabled_hook_skipped(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        h = WorkflowHook(
            hook_id="h1",
            project_id="p1",
            name="disabled",
            event_pattern="*",
            enabled=False,
        )
        engine.register(h)

        await engine.handle(_evt())
        assert engine.stats["triggered"] == 0

    async def test_conditions_filter(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="*", conditions={"stage": "review"}))

        await engine.handle(_evt(stage="deploy"))
        assert engine.stats["triggered"] == 0

        await engine.handle(_evt(stage="review"))
        assert engine.stats["triggered"] == 1

    async def test_on_trigger_callback(self) -> None:
        triggered: list[str] = []

        async def cb(hook: WorkflowHook, event: EventEnvelope, params: dict[str, Any]) -> None:
            triggered.append(hook.hook_id)

        engine = HookEngine(on_trigger=cb)
        h = _hook(event_pattern="*")
        engine.register(h)

        await engine.handle(_evt())
        assert len(triggered) == 1

    async def test_on_trigger_failure_emits_event(self) -> None:
        bus = FakeEventBus()

        async def bad_cb(hook: WorkflowHook, event: EventEnvelope, params: dict[str, Any]) -> None:
            msg = "boom"
            raise RuntimeError(msg)

        engine = HookEngine(event_bus=bus, on_trigger=bad_cb)
        engine.register(_hook(event_pattern="*"))

        await engine.handle(_evt())
        from lintel.domain.events import HookExecutionFailed

        failed = [e for e in bus.published if isinstance(e, HookExecutionFailed)]
        assert len(failed) == 1


# ---------------------------------------------------------------------------
# Pre-hook tests
# ---------------------------------------------------------------------------


class TestPreHookEvaluation:
    async def test_pre_hook_default_allows(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="*", hook_type=HookType.PRE))

        await engine.handle(_evt())

        allowed = [e for e in bus.published if isinstance(e, PreHookAllowed)]
        assert len(allowed) == 1
        assert engine.stats["pre_denied"] == 0

    async def test_pre_hook_deny_via_evaluator(self) -> None:
        bus = FakeEventBus()

        async def deny_all(hook: WorkflowHook, event: EventEnvelope) -> tuple[PreHookDecision, str]:
            return PreHookDecision.DENY, "policy violation"

        engine = HookEngine(event_bus=bus, pre_hook_evaluator=deny_all)
        engine.register(_hook(event_pattern="*", hook_type=HookType.PRE))

        await engine.handle(_evt())

        blocked = [e for e in bus.published if isinstance(e, PreHookBlocked)]
        assert len(blocked) == 1
        assert blocked[0].payload["reason"] == "policy violation"
        assert engine.stats["pre_denied"] == 1

    async def test_pre_hook_evaluator_error_defaults_allow(self) -> None:
        bus = FakeEventBus()

        async def bad_eval(hook: WorkflowHook, event: EventEnvelope) -> tuple[PreHookDecision, str]:
            msg = "oops"
            raise RuntimeError(msg)

        engine = HookEngine(event_bus=bus, pre_hook_evaluator=bad_eval)
        engine.register(_hook(event_pattern="*", hook_type=HookType.PRE))

        await engine.handle(_evt())

        allowed = [e for e in bus.published if isinstance(e, PreHookAllowed)]
        assert len(allowed) == 1

    async def test_evaluate_pre_hooks_returns_results(self) -> None:
        async def deny_all(hook: WorkflowHook, event: EventEnvelope) -> tuple[PreHookDecision, str]:
            return PreHookDecision.DENY, "nope"

        engine = HookEngine(pre_hook_evaluator=deny_all)
        h = _hook(event_pattern="*", hook_type=HookType.PRE)
        engine.register(h)

        results = await engine.evaluate_pre_hooks(_evt())
        assert len(results) == 1
        assert isinstance(results[0], HookResult)
        assert results[0].decision == PreHookDecision.DENY
        assert results[0].reason == "nope"

    async def test_evaluate_pre_hooks_skips_post_hooks(self) -> None:
        engine = HookEngine()
        engine.register(_hook(event_pattern="*", hook_type=HookType.POST))

        results = await engine.evaluate_pre_hooks(_evt())
        assert results == []


# ---------------------------------------------------------------------------
# Chain depth / loop protection
# ---------------------------------------------------------------------------


class TestChainDepth:
    async def test_loop_blocked(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="*", max_chain_depth=2))

        await engine.handle(_evt(__hook_chain_depth=2))

        assert engine.stats["triggered"] == 0
        assert engine.stats["blocked_loops"] == 1
        loop = [e for e in bus.published if isinstance(e, HookLoopDetected)]
        assert len(loop) == 1

    async def test_within_depth_allowed(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="*", max_chain_depth=5))

        await engine.handle(_evt(__hook_chain_depth=3))
        assert engine.stats["triggered"] == 1

    async def test_skips_own_events(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        engine.register(_hook(event_pattern="*"))

        for et in (
            "HookTriggered",
            "HookExecutionFailed",
            "HookLoopDetected",
            "PreHookBlocked",
            "PreHookAllowed",
        ):
            await engine.handle(_evt(event_type=et))

        assert engine.stats["triggered"] == 0


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_start_subscribes(self) -> None:
        bus = FakeEventBus()
        engine = HookEngine(event_bus=bus)
        await engine.start()
        assert engine._subscription_id == "sub-1"

    async def test_register_unregister(self) -> None:
        engine = HookEngine()
        h = _hook()
        engine.register(h)
        assert engine.stats["hooks_registered"] == 1
        engine.unregister(h.hook_id)
        assert engine.stats["hooks_registered"] == 0


# ---------------------------------------------------------------------------
# Webhook action type
# ---------------------------------------------------------------------------


class TestHookActionTypes:
    def test_webhook_hook_type(self) -> None:
        h = _hook(
            action_type=HookActionType.WEBHOOK,
            webhook_url="https://example.com/hook",
        )
        assert h.action_type == HookActionType.WEBHOOK
        assert h.webhook_url == "https://example.com/hook"

    def test_trigger_workflow_default(self) -> None:
        h = _hook()
        assert h.action_type == HookActionType.TRIGGER_WORKFLOW
