"""Workflow Hook Manager — evaluates hooks against domain events and triggers workflows.

Subscribes to all events via the EventBus. When an event matches a hook's
event_pattern and conditions, the hook fires and triggers the bound workflow.
Includes circuit breaker for infinite loop prevention.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus
    from lintel.domain.types import WorkflowHook

logger = structlog.get_logger()

# Internal header to track chain depth through event payloads.
_CHAIN_DEPTH_KEY = "__hook_chain_depth"


class HookManager:
    """Evaluates workflow hooks against domain events.

    Implements the EventHandler protocol (``handle(event)``).
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        on_trigger: Any | None = None,  # noqa: ANN401
    ) -> None:
        self._event_bus = event_bus
        self._hooks: dict[str, WorkflowHook] = {}
        self._subscription_id: str | None = None
        # Callback: async (hook, event, params) -> None
        self._on_trigger = on_trigger
        self._triggered_count = 0
        self._blocked_count = 0

    async def start(self) -> None:
        """Subscribe to all events on the bus."""
        if self._event_bus is None:
            return
        # Empty frozenset = receive all events.
        self._subscription_id = await self._event_bus.subscribe(
            frozenset(),
            self,
        )
        logger.info("hook_manager_started", subscription_id=self._subscription_id)

    async def stop(self) -> None:
        if self._event_bus is not None and self._subscription_id is not None:
            await self._event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    def register(self, hook: WorkflowHook) -> None:
        """Register a hook for evaluation."""
        self._hooks[hook.hook_id] = hook

    def unregister(self, hook_id: str) -> None:
        self._hooks.pop(hook_id, None)

    async def handle(self, event: EventEnvelope) -> None:
        """EventHandler protocol — evaluate all hooks against this event."""
        # Skip our own events to avoid recursion.
        if event.event_type in ("HookTriggered", "HookExecutionFailed", "HookLoopDetected"):
            return

        chain_depth = event.payload.get(_CHAIN_DEPTH_KEY, 0)
        if not isinstance(chain_depth, int):
            chain_depth = 0

        for hook in list(self._hooks.values()):
            if not hook.enabled:
                continue
            if not _pattern_matches(hook.event_pattern, event.event_type):
                continue
            if hook.conditions and not _conditions_match(hook.conditions, event.payload):
                continue

            # Chain depth check.
            if chain_depth >= hook.max_chain_depth:
                self._blocked_count += 1
                logger.warning(
                    "hook_loop_detected",
                    hook_id=hook.hook_id,
                    event_type=event.event_type,
                    chain_depth=chain_depth,
                )
                if self._event_bus is not None:
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
                continue

            # Build params from template.
            params = _resolve_params(hook.params_template, event.payload)
            params[_CHAIN_DEPTH_KEY] = chain_depth + 1

            self._triggered_count += 1
            logger.info(
                "hook_triggered",
                hook_id=hook.hook_id,
                hook_name=hook.name,
                event_type=event.event_type,
                workflow_id=hook.workflow_id,
            )

            if self._event_bus is not None:
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

            if self._on_trigger is not None:
                try:
                    await self._on_trigger(hook, event, params)
                except Exception:
                    logger.warning(
                        "hook_execution_failed",
                        hook_id=hook.hook_id,
                        exc_info=True,
                    )
                    if self._event_bus is not None:
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

    @property
    def stats(self) -> dict[str, int]:
        return {
            "hooks_registered": len(self._hooks),
            "triggered": self._triggered_count,
            "blocked_loops": self._blocked_count,
        }


def _pattern_matches(pattern: str, event_type: str) -> bool:
    """Match a hook event pattern against an event type.

    Supports: exact match, fnmatch globs (*, ?, [seq]).
    Examples: "PipelineRunCompleted", "Pipeline*", "*.Completed"
    """
    if not pattern or pattern == "*":
        return True
    return fnmatch.fnmatch(event_type, pattern)


def _conditions_match(conditions: dict[str, object], payload: dict[str, Any]) -> bool:
    """Check if all conditions match the event payload.

    Simple equality check on top-level keys.
    """
    for key, expected in conditions.items():
        actual = payload.get(key)
        if actual != expected:
            return False
    return True


def _resolve_params(
    template: dict[str, str] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Resolve parameter template against event payload.

    Template values like "{{ event.field_name }}" are replaced with
    the actual payload value. Plain strings are passed through.
    """
    if not template:
        return {}
    result: dict[str, Any] = {}
    for key, value in template.items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            field = value.strip("{ }").replace("event.", "", 1)
            result[key] = payload.get(field, "")
        else:
            result[key] = value
    return result
