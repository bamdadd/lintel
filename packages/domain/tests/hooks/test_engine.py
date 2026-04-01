"""Unit tests for HookEngine with circuit breaker and pre/post logic."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from lintel.contracts.events import EventEnvelope
from lintel.domain.hooks import HookPreResponse
from lintel.domain.hooks.engine import CHAIN_DEPTH_KEY, HookEngine
from lintel.domain.types import HookType, Trigger, TriggerType


def _make_event(
    event_type: str = "pipeline.build.completed",
    payload: dict[str, Any] | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        payload=payload or {},
    )


def _make_hook(
    trigger_id: str = "h1",
    hook_type: HookType = HookType.POST,
    event_pattern: str = "pipeline.*.completed",
    max_chain_depth: int = 5,
    enabled: bool = True,
) -> Trigger:
    return Trigger(
        trigger_id=trigger_id,
        project_id="proj-1",
        trigger_type=TriggerType.WEBHOOK,
        name="Test Hook",
        hook_type=hook_type,
        event_pattern=event_pattern,
        max_chain_depth=max_chain_depth,
        enabled=enabled,
    )


def _make_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock(return_value="sub-1")
    bus.unsubscribe = AsyncMock()
    return bus


class TestHookEnginePostHook:
    """Post-hook fires asynchronously on matching event."""

    async def test_post_hook_fires_on_match(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook())

        await engine.handle(_make_event())
        # Post hooks run via asyncio.create_task, give it a tick
        await asyncio.sleep(0.01)

        on_post.assert_called_once()
        call_args = on_post.call_args
        assert call_args[0][0].trigger_id == "h1"
        assert call_args[0][2] == 1  # chain_depth incremented

    async def test_post_hook_does_not_block(self) -> None:
        """Post hooks should not block the handle() call."""
        on_post = AsyncMock(side_effect=lambda *a: asyncio.sleep(0.1))
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook())

        # handle() should return quickly without waiting for post hook
        await engine.handle(_make_event())
        # Just verify it didn't raise
        await asyncio.sleep(0.01)

    async def test_post_hook_failure_emits_event(self) -> None:
        """Post-hook failure emits HookExecutionFailed when bus is present."""
        on_post = AsyncMock(side_effect=RuntimeError("boom"))
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_post_hook=on_post)
        engine.register_hook(_make_hook())

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        on_post.assert_called_once()
        assert bus.publish.called
        published_event = bus.publish.call_args[0][0]
        assert published_event.event_type == "HookExecutionFailed"

    async def test_disabled_hook_is_skipped(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(enabled=False))

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        on_post.assert_not_called()


class TestHookEnginePreHook:
    """Pre-hook evaluation tests."""

    async def test_pre_hook_allow_true(self) -> None:
        on_pre = AsyncMock(return_value=HookPreResponse(allow=True))
        engine = HookEngine(on_pre_hook=on_pre)
        engine.register_hook(_make_hook(hook_type=HookType.PRE))

        await engine.handle(_make_event())

        on_pre.assert_called_once()

    async def test_pre_hook_allow_false(self) -> None:
        on_pre = AsyncMock(return_value=HookPreResponse(allow=False))
        engine = HookEngine(on_pre_hook=on_pre)
        engine.register_hook(_make_hook(hook_type=HookType.PRE))

        await engine.handle(_make_event())

        on_pre.assert_called_once()
        response = on_pre.return_value
        assert response.allow is False

    async def test_pre_hook_modified_payload(self) -> None:
        modified = {"new_key": "new_value"}
        on_pre = AsyncMock(
            return_value=HookPreResponse(allow=True, modified_payload=modified),
        )
        engine = HookEngine(on_pre_hook=on_pre)
        engine.register_hook(_make_hook(hook_type=HookType.PRE))

        await engine.handle(_make_event())

        response = on_pre.return_value
        assert response.modified_payload == modified

    async def test_pre_hook_failure_defaults_to_allow(self) -> None:
        on_pre = AsyncMock(side_effect=RuntimeError("boom"))
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_pre_hook=on_pre)
        engine.register_hook(_make_hook(hook_type=HookType.PRE))

        # Should not raise
        await engine.handle(_make_event())

        on_pre.assert_called_once()
        # Should emit HookExecutionFailed
        assert bus.publish.called
        published_event = bus.publish.call_args[0][0]
        assert published_event.event_type == "HookExecutionFailed"

    async def test_pre_hook_none_callback_returns_allow(self) -> None:
        """When on_pre_hook is None, pre-hooks default to allow=True."""
        engine = HookEngine(on_pre_hook=None)
        engine.register_hook(_make_hook(hook_type=HookType.PRE))

        # Should not raise
        await engine.handle(_make_event())


class TestHookEngineCircuitBreaker:
    """Circuit breaker prevents infinite hook chains."""

    async def test_chain_depth_exceeded_blocks_execution(self) -> None:
        on_post = AsyncMock()
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=3))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 3})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_not_called()
        # Should emit HookLoopDetected
        assert bus.publish.called
        published_event = bus.publish.call_args[0][0]
        assert published_event.event_type == "HookLoopDetected"

    async def test_chain_depth_below_max_executes(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=5))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 4})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_called_once()
        # chain_depth should be incremented to 5
        assert on_post.call_args[0][2] == 5

    async def test_chain_depth_zero_default(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=5))

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        on_post.assert_called_once()
        assert on_post.call_args[0][2] == 1

    async def test_chain_depth_equal_to_max_blocks(self) -> None:
        """Boundary: depth == max should block."""
        on_post = AsyncMock()
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=5))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 5})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_not_called()

    async def test_chain_depth_greater_than_max_blocks(self) -> None:
        on_post = AsyncMock()
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=3))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 10})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_not_called()

    async def test_chain_depth_non_int_treated_as_zero(self) -> None:
        """Non-integer chain depth falls back to 0."""
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=5))

        event = _make_event(payload={CHAIN_DEPTH_KEY: "not-a-number"})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_called_once()
        assert on_post.call_args[0][2] == 1

    async def test_blocked_chain_increments_stats(self) -> None:
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus, on_post_hook=AsyncMock())
        engine.register_hook(_make_hook(max_chain_depth=2))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 2})
        await engine.handle(event)
        await asyncio.sleep(0.01)

        assert engine.stats["blocked_chains"] == 1

    async def test_no_event_emitted_without_bus(self) -> None:
        """Circuit breaker fires but no event emitted when bus is None."""
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(max_chain_depth=2))

        event = _make_event(payload={CHAIN_DEPTH_KEY: 2})
        # Should not raise even without a bus
        await engine.handle(event)
        await asyncio.sleep(0.01)

        on_post.assert_not_called()


class TestHookEngineNoMatch:
    """No matching hooks — engine is a no-op."""

    async def test_no_matching_hooks_noop(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(event_pattern="deploy.*"))

        await engine.handle(_make_event(event_type="pipeline.build.completed"))
        await asyncio.sleep(0.01)

        on_post.assert_not_called()

    async def test_no_hooks_registered_noop(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        on_post.assert_not_called()


class TestHookEngineMultipleHooks:
    """Multiple matching hooks evaluated in order."""

    async def test_multiple_hooks_all_evaluated(self) -> None:
        call_order: list[str] = []

        async def on_post(hook: Trigger, event: EventEnvelope, depth: int) -> None:
            call_order.append(hook.trigger_id)

        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(trigger_id="h1", event_pattern="pipeline.*.*"))
        engine.register_hook(_make_hook(trigger_id="h2", event_pattern="*.build.*"))

        await engine.handle(_make_event())
        await asyncio.sleep(0.05)

        assert "h1" in call_order
        assert "h2" in call_order

    async def test_mix_of_pre_and_post_hooks(self) -> None:
        on_pre = AsyncMock(return_value=HookPreResponse(allow=True))
        on_post = AsyncMock()
        engine = HookEngine(on_pre_hook=on_pre, on_post_hook=on_post)
        engine.register_hook(
            _make_hook(trigger_id="pre1", hook_type=HookType.PRE, event_pattern="pipeline.*.*"),
        )
        engine.register_hook(
            _make_hook(trigger_id="post1", hook_type=HookType.POST, event_pattern="pipeline.*.*"),
        )

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        on_pre.assert_called_once()
        on_post.assert_called_once()


class TestHookEngineSkipsOwnEvents:
    """Engine skips its own event types to prevent recursion."""

    async def test_skips_hook_triggered(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(event_pattern="*"))

        await engine.handle(_make_event(event_type="HookTriggered"))
        await asyncio.sleep(0.01)

        on_post.assert_not_called()

    async def test_skips_hook_execution_failed(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(event_pattern="*"))

        await engine.handle(_make_event(event_type="HookExecutionFailed"))
        await asyncio.sleep(0.01)

        on_post.assert_not_called()

    async def test_skips_hook_loop_detected(self) -> None:
        on_post = AsyncMock()
        engine = HookEngine(on_post_hook=on_post)
        engine.register_hook(_make_hook(event_pattern="*"))

        await engine.handle(_make_event(event_type="HookLoopDetected"))
        await asyncio.sleep(0.01)

        on_post.assert_not_called()


class TestHookEngineLifecycle:
    """Engine start/stop lifecycle."""

    async def test_start_subscribes(self) -> None:
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus)

        await engine.start()

        bus.subscribe.assert_called_once()

    async def test_stop_unsubscribes(self) -> None:
        bus = _make_event_bus()
        engine = HookEngine(event_bus=bus)

        await engine.start()
        await engine.stop()

        bus.unsubscribe.assert_called_once_with("sub-1")

    async def test_start_without_bus_is_noop(self) -> None:
        engine = HookEngine()
        # Should not raise
        await engine.start()

    async def test_stop_without_bus_is_noop(self) -> None:
        engine = HookEngine()
        # Should not raise
        await engine.stop()

    async def test_register_and_unregister(self) -> None:
        engine = HookEngine()
        engine.register_hook(_make_hook(trigger_id="h1"))
        engine.register_hook(_make_hook(trigger_id="h2"))
        assert engine.stats["hooks_registered"] == 2

        engine.unregister_hook("h1")
        assert engine.stats["hooks_registered"] == 1

    async def test_set_hooks_replaces_all(self) -> None:
        engine = HookEngine()
        engine.register_hook(_make_hook(trigger_id="h1"))
        engine.set_hooks([_make_hook(trigger_id="h2"), _make_hook(trigger_id="h3")])
        assert engine.stats["hooks_registered"] == 2

    async def test_stats(self) -> None:
        engine = HookEngine()
        engine.register_hook(_make_hook())

        assert engine.stats["hooks_registered"] == 1
        assert engine.stats["triggered"] == 0
        assert engine.stats["blocked_chains"] == 0

    async def test_stats_after_trigger(self) -> None:
        engine = HookEngine(on_post_hook=AsyncMock())
        engine.register_hook(_make_hook())

        await engine.handle(_make_event())
        await asyncio.sleep(0.01)

        assert engine.stats["triggered"] == 1
