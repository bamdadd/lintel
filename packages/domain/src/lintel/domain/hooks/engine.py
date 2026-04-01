"""Hook engine — evaluates hooks against domain events with circuit breaker.

Subscribes to events via the EventBus, matches against registered hooks,
and invokes handlers for pre-hooks (blocking) and post-hooks (async).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from lintel.domain.hooks import HookPreResponse
from lintel.domain.hooks.matcher import find_matching_hooks
from lintel.domain.types import HookType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus, EventStore
    from lintel.domain.types import Trigger

logger = structlog.get_logger()

# Internal key to track chain depth through event payloads.
CHAIN_DEPTH_KEY = "__hook_chain_depth"


class HookEngine:
    """Evaluates hooks against domain events with circuit breaker protection.

    Implements the EventHandler protocol (handle(event)).

    Pre-hooks are evaluated synchronously and can block/modify the action.
    Post-hooks are invoked asynchronously without blocking the caller.
    Circuit breaker prevents infinite hook chains by tracking chain depth.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        event_store: EventStore | None = None,
        on_pre_hook: (
            Callable[[Trigger, EventEnvelope, int], Awaitable[HookPreResponse]] | None
        ) = None,
        on_post_hook: (Callable[[Trigger, EventEnvelope, int], Awaitable[None]] | None) = None,
    ) -> None:
        self._event_bus = event_bus
        self._event_store = event_store
        self._hooks: list[Trigger] = []
        self._subscription_id: str | None = None
        self._on_pre_hook = on_pre_hook
        self._on_post_hook = on_post_hook
        self._triggered_count = 0
        self._blocked_count = 0
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        """Subscribe to all events on the bus."""
        if self._event_bus is None:
            return
        self._subscription_id = await self._event_bus.subscribe(
            frozenset(),
            self,
        )
        logger.info("hook_engine_started", subscription_id=self._subscription_id)

    async def stop(self) -> None:
        """Unsubscribe from the event bus."""
        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    def register_hook(self, hook: Trigger) -> None:
        """Register a trigger with hook fields for evaluation."""
        self._hooks.append(hook)

    def unregister_hook(self, trigger_id: str) -> None:
        """Remove a hook by trigger_id."""
        self._hooks = [h for h in self._hooks if h.trigger_id != trigger_id]

    def set_hooks(self, hooks: list[Trigger]) -> None:
        """Replace all registered hooks."""
        self._hooks = list(hooks)

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — evaluate all hooks against this event."""
        if event.event_type in (
            "HookTriggered",
            "HookExecutionFailed",
            "HookLoopDetected",
        ):
            return

        chain_depth = event.payload.get(CHAIN_DEPTH_KEY, 0)
        if not isinstance(chain_depth, int):
            chain_depth = 0

        matching = find_matching_hooks(event.event_type, self._hooks)
        if not matching:
            return

        for hook in matching:
            if chain_depth >= hook.max_chain_depth:
                self._blocked_count += 1
                logger.warning(
                    "hook_chain_depth_exceeded",
                    trigger_id=hook.trigger_id,
                    event_type=event.event_type,
                    chain_depth=chain_depth,
                    max_chain_depth=hook.max_chain_depth,
                )
                await self._emit_chain_depth_exceeded(hook, event, chain_depth)
                continue

            next_depth = chain_depth + 1
            self._triggered_count += 1

            if hook.hook_type == HookType.PRE:
                await self._execute_pre_hook(hook, event, next_depth)
            elif hook.hook_type == HookType.POST:
                self._execute_post_hook(hook, event, next_depth)

    async def _execute_pre_hook(
        self,
        hook: Trigger,
        event: EventEnvelope,
        chain_depth: int,
    ) -> HookPreResponse:
        """Execute a pre-hook synchronously and return the response."""
        if self._on_pre_hook is None:
            return HookPreResponse(allow=True)

        try:
            response = await self._on_pre_hook(hook, event, chain_depth)
        except Exception:
            logger.warning(
                "pre_hook_execution_failed",
                trigger_id=hook.trigger_id,
                exc_info=True,
            )
            await self._emit_execution_failed(hook, event)
            return HookPreResponse(allow=True)

        logger.info(
            "pre_hook_evaluated",
            trigger_id=hook.trigger_id,
            event_type=event.event_type,
            allow=response.allow,
            has_modified_payload=response.modified_payload is not None,
        )
        return response

    def _execute_post_hook(
        self,
        hook: Trigger,
        event: EventEnvelope,
        chain_depth: int,
    ) -> None:
        """Fire a post-hook asynchronously without blocking."""
        task = asyncio.create_task(self._run_post_hook(hook, event, chain_depth))
        # Store reference to prevent GC of the task.
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_post_hook(
        self,
        hook: Trigger,
        event: EventEnvelope,
        chain_depth: int,
    ) -> None:
        """Execute a post-hook and handle errors."""
        if self._on_post_hook is None:
            return

        try:
            await self._on_post_hook(hook, event, chain_depth)
        except Exception:
            logger.warning(
                "post_hook_execution_failed",
                trigger_id=hook.trigger_id,
                exc_info=True,
            )
            await self._emit_execution_failed(hook, event)
            return

        logger.info(
            "post_hook_fired",
            trigger_id=hook.trigger_id,
            event_type=event.event_type,
            chain_depth=chain_depth,
        )

    async def _emit_chain_depth_exceeded(
        self,
        hook: Trigger,
        event: EventEnvelope,
        chain_depth: int,
    ) -> None:
        """Emit a hook.chain_depth_exceeded event to the event store."""
        if self._event_bus is None:
            return

        from lintel.domain.events import HookLoopDetected

        await self._event_bus.publish(
            HookLoopDetected(
                payload={
                    "trigger_id": hook.trigger_id,
                    "event_type": event.event_type,
                    "chain_depth": chain_depth,
                    "max_chain_depth": hook.max_chain_depth,
                },
                correlation_id=event.correlation_id,
            )
        )

    async def _emit_execution_failed(
        self,
        hook: Trigger,
        event: EventEnvelope,
    ) -> None:
        """Emit a hook execution failed event."""
        if self._event_bus is None:
            return

        from lintel.domain.events import HookExecutionFailed

        await self._event_bus.publish(
            HookExecutionFailed(
                payload={
                    "trigger_id": hook.trigger_id,
                    "event_type": event.event_type,
                    "error": "hook execution failed",
                },
                correlation_id=event.correlation_id,
            )
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Return hook engine statistics."""
        return {
            "hooks_registered": len(self._hooks),
            "triggered": self._triggered_count,
            "blocked_chains": self._blocked_count,
        }
