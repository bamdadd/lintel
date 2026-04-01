"""HookEngine — evaluates pre and post hooks against domain events.

Pre-hooks run synchronously before the event proceeds and can block it
(return ``PreHookDecision.DENY``).  Post-hooks are fire-and-forget
notifications triggered after the event is accepted.

The engine subscribes to the EventBus (``handle`` implements the
``EventHandler`` protocol) and delegates pattern matching to
:mod:`lintel.domain.hooks.pattern`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

from lintel.domain.hooks.pattern import conditions_match, matches_event_pattern, resolve_params
from lintel.domain.types import HookResult, HookType, PreHookDecision

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus
    from lintel.domain.types import WorkflowHook

logger = structlog.get_logger()

# Payload key tracking hook chain depth for loop prevention.
_CHAIN_DEPTH_KEY = "__hook_chain_depth"

# Hook-generated events we must never react to (prevent recursion).
_SKIP_EVENT_TYPES = frozenset(
    {
        "HookTriggered",
        "HookExecutionFailed",
        "HookLoopDetected",
        "PreHookBlocked",
        "PreHookAllowed",
    }
)


class OnTriggerCallback(Protocol):
    """Async callback invoked when a post-hook fires."""

    async def __call__(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
        params: dict[str, Any],
    ) -> None: ...


class PreHookEvaluator(Protocol):
    """Async callback for pre-hook evaluation.

    Returns a ``PreHookDecision`` and an optional reason string.
    If not provided the engine uses the default allow/deny logic
    based on hook conditions.
    """

    async def __call__(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
    ) -> tuple[PreHookDecision, str]: ...


class HookEngine:
    """Evaluate workflow hooks against domain events.

    Separates pre-hooks (synchronous allow/deny) from post-hooks
    (fire-and-forget callbacks).
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        on_trigger: OnTriggerCallback | None = None,
        pre_hook_evaluator: PreHookEvaluator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._hooks: dict[str, WorkflowHook] = {}
        self._subscription_id: str | None = None
        self._on_trigger = on_trigger
        self._pre_hook_evaluator = pre_hook_evaluator

        # Counters for diagnostics.
        self._triggered_count = 0
        self._blocked_count = 0
        self._pre_denied_count = 0

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Subscribe to all events on the bus."""
        if self._event_bus is None:
            return
        self._subscription_id = await self._event_bus.subscribe(frozenset(), self)
        logger.info("hook_engine_started", subscription_id=self._subscription_id)

    async def stop(self) -> None:
        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    def register(self, hook: WorkflowHook) -> None:
        """Register a hook for evaluation."""
        self._hooks[hook.hook_id] = hook

    def unregister(self, hook_id: str) -> None:
        self._hooks.pop(hook_id, None)

    # -- EventHandler protocol -----------------------------------------------

    async def handle(self, event: EventEnvelope) -> None:
        """Evaluate all hooks against *event*."""
        if event.event_type in _SKIP_EVENT_TYPES:
            return

        chain_depth = event.payload.get(_CHAIN_DEPTH_KEY, 0)
        if not isinstance(chain_depth, int):
            chain_depth = 0

        for hook in list(self._hooks.values()):
            if not hook.enabled:
                continue
            if not matches_event_pattern(hook.event_pattern, event.event_type):
                continue
            if hook.conditions and not conditions_match(hook.conditions, event.payload):
                continue

            if chain_depth >= hook.max_chain_depth:
                await self._emit_loop_detected(hook, event, chain_depth)
                continue

            if hook.hook_type == HookType.PRE:
                await self._evaluate_pre_hook(hook, event)
            else:
                await self._fire_post_hook(hook, event, chain_depth)

    # -- pre-hook evaluation -------------------------------------------------

    async def evaluate_pre_hooks(self, event: EventEnvelope) -> list[HookResult]:
        """Evaluate all matching pre-hooks and return results.

        This can be called explicitly before committing an action
        to check whether any pre-hook would deny it.
        """
        results: list[HookResult] = []
        for hook in list(self._hooks.values()):
            if not hook.enabled or hook.hook_type != HookType.PRE:
                continue
            if not matches_event_pattern(hook.event_pattern, event.event_type):
                continue
            if hook.conditions and not conditions_match(hook.conditions, event.payload):
                continue

            decision, reason = await self._run_pre_hook(hook, event)
            results.append(
                HookResult(
                    hook_id=hook.hook_id,
                    hook_name=hook.name,
                    hook_type=HookType.PRE,
                    decision=decision,
                    reason=reason,
                )
            )
        return results

    async def _evaluate_pre_hook(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
    ) -> None:
        decision, reason = await self._run_pre_hook(hook, event)
        if decision == PreHookDecision.DENY:
            self._pre_denied_count += 1
            logger.info(
                "pre_hook_denied",
                hook_id=hook.hook_id,
                event_type=event.event_type,
                reason=reason,
            )
            await self._emit_pre_hook_blocked(hook, event, reason)
        else:
            await self._emit_pre_hook_allowed(hook, event)

    async def _run_pre_hook(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
    ) -> tuple[PreHookDecision, str]:
        if self._pre_hook_evaluator is not None:
            try:
                return await self._pre_hook_evaluator(hook, event)
            except Exception:
                logger.warning(
                    "pre_hook_evaluator_error",
                    hook_id=hook.hook_id,
                    exc_info=True,
                )
                return PreHookDecision.ALLOW, "evaluator error — defaulting to allow"
        # Default: conditions already matched, so allow.
        return PreHookDecision.ALLOW, ""

    # -- post-hook fire ------------------------------------------------------

    async def _fire_post_hook(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
        chain_depth: int,
    ) -> None:
        params = resolve_params(hook.params_template, event.payload)
        params[_CHAIN_DEPTH_KEY] = chain_depth + 1

        self._triggered_count += 1
        logger.info(
            "hook_triggered",
            hook_id=hook.hook_id,
            hook_name=hook.name,
            event_type=event.event_type,
            workflow_id=hook.workflow_id,
        )

        await self._emit_hook_triggered(hook, event, params)

        if self._on_trigger is not None:
            try:
                await self._on_trigger(hook, event, params)
            except Exception:
                logger.warning(
                    "hook_execution_failed",
                    hook_id=hook.hook_id,
                    exc_info=True,
                )
                await self._emit_hook_execution_failed(hook, event)

    # -- event emission helpers ----------------------------------------------

    async def _emit_hook_triggered(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
        params: dict[str, Any],
    ) -> None:
        if self._event_bus is None:
            return
        from lintel.domain.events import HookTriggered

        await self._event_bus.publish(
            HookTriggered(
                payload={
                    "hook_id": hook.hook_id,
                    "event_type": event.event_type,
                    "workflow_id": hook.workflow_id,
                    "params": params,
                },
                correlation_id=event.correlation_id,
            )
        )

    async def _emit_hook_execution_failed(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
    ) -> None:
        if self._event_bus is None:
            return
        from lintel.domain.events import HookExecutionFailed

        await self._event_bus.publish(
            HookExecutionFailed(
                payload={
                    "hook_id": hook.hook_id,
                    "event_type": event.event_type,
                    "error": "on_trigger callback failed",
                },
                correlation_id=event.correlation_id,
            )
        )

    async def _emit_loop_detected(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
        chain_depth: int,
    ) -> None:
        self._blocked_count += 1
        logger.warning(
            "hook_loop_detected",
            hook_id=hook.hook_id,
            event_type=event.event_type,
            chain_depth=chain_depth,
        )
        if self._event_bus is None:
            return
        from lintel.domain.events import HookLoopDetected

        await self._event_bus.publish(
            HookLoopDetected(
                payload={
                    "hook_id": hook.hook_id,
                    "event_type": event.event_type,
                    "chain_depth": chain_depth,
                },
                correlation_id=event.correlation_id,
            )
        )

    async def _emit_pre_hook_blocked(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
        reason: str,
    ) -> None:
        if self._event_bus is None:
            return
        from lintel.domain.events import PreHookBlocked

        await self._event_bus.publish(
            PreHookBlocked(
                payload={
                    "hook_id": hook.hook_id,
                    "hook_name": hook.name,
                    "event_type": event.event_type,
                    "reason": reason,
                },
                correlation_id=event.correlation_id,
            )
        )

    async def _emit_pre_hook_allowed(
        self,
        hook: WorkflowHook,
        event: EventEnvelope,
    ) -> None:
        if self._event_bus is None:
            return
        from lintel.domain.events import PreHookAllowed

        await self._event_bus.publish(
            PreHookAllowed(
                payload={
                    "hook_id": hook.hook_id,
                    "hook_name": hook.name,
                    "event_type": event.event_type,
                },
                correlation_id=event.correlation_id,
            )
        )

    # -- diagnostics ---------------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        return {
            "hooks_registered": len(self._hooks),
            "triggered": self._triggered_count,
            "blocked_loops": self._blocked_count,
            "pre_denied": self._pre_denied_count,
        }
