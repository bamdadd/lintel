"""HumanInterruptNode — shared base class for LangGraph human-in-the-loop nodes.

Used by F013 (editable reports), F017 (approval gates), and F018 (human tasks).
Extends the existing async-function node pattern with a class that manages the
full interrupt/resume lifecycle:

1. Build InterruptRequest from node config
2. Persist to InterruptRepository
3. Publish HumanInterruptRequested event
4. Call ``langgraph.types.interrupt()`` to pause the graph
5. On resume, call ``process_resume()`` (implemented by subclasses)
6. Publish HumanInterruptResumed event
"""

from __future__ import annotations

import abc
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from langgraph.types import Command, interrupt
import structlog

from lintel.workflows.events import HumanInterruptRequested, HumanInterruptResumed
from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE, StageTracker
from lintel.workflows.types import (
    InterruptRequest,
    InterruptType,
    TimeoutSentinel,
)

if TYPE_CHECKING:
    from lintel.workflows.repositories.interrupt_repository import InterruptRepository

logger = structlog.get_logger()


class HumanInterruptNode(abc.ABC):
    """Abstract base for workflow nodes that pause for human input.

    Subclasses must implement:
    - ``interrupt_type`` — which kind of interrupt this is
    - ``timeout_seconds`` — how long to wait before timeout (0 = no timeout)
    - ``on_timeout`` — what to do when the deadline passes
    - ``process_resume(state, human_input)`` — handle the human's response

    Usage in a LangGraph graph::

        node = ApprovalGateNode(node_name="approval_gate_research")
        graph.add_node("approval_gate_research", node)
    """

    def __init__(
        self,
        node_name: str,
        *,
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        self.node_name = node_name
        self.channel_config = channel_config

    # --- Abstract interface for subclasses ---

    @property
    @abc.abstractmethod
    def interrupt_type(self) -> InterruptType:
        """The type of human interrupt this node represents."""

    @property
    @abc.abstractmethod
    def timeout_seconds(self) -> int:
        """Seconds to wait before auto-timeout. 0 means no timeout."""

    @property
    @abc.abstractmethod
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        """Behaviour when the interrupt deadline passes."""

    @abc.abstractmethod
    def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Handle the human-supplied input and return state updates.

        Called after the graph is resumed.  Must return a dict of state
        updates (same contract as a regular LangGraph node function).
        """

    # --- Public callable (LangGraph node protocol) ---

    async def __call__(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | Command[Any]:
        """Execute the interrupt lifecycle.

        This method is registered as the LangGraph node function.
        """
        config = config or {}
        configurable = config.get("configurable", {})
        run_id = str(configurable.get("run_id", "") or state.get("run_id", ""))
        stage = NODE_TO_STAGE.get(self.node_name, self.node_name)

        # Stage tracking
        tracker = StageTracker(config, state)
        await tracker.mark_running(self.node_name)
        await tracker.append_log(self.node_name, f"Requesting human input ({self.interrupt_type})")

        # Build request
        deadline = None
        if self.timeout_seconds > 0:
            deadline = datetime.now(tz=UTC) + timedelta(seconds=self.timeout_seconds)

        request = InterruptRequest(
            id=uuid4(),
            run_id=run_id,
            stage=stage,
            interrupt_type=self.interrupt_type,
            payload=self._build_payload(state),
            timeout_seconds=self.timeout_seconds,
            deadline=deadline,
        )

        # Persist interrupt record
        interrupt_repo: InterruptRepository | None = configurable.get("interrupt_repository")
        if interrupt_repo is None:
            # Try runtime registry fallback
            app_state = configurable.get("app_state")
            if app_state is None and run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                app_state = get_app_state(run_id)
            if app_state is not None:
                interrupt_repo = getattr(app_state, "interrupt_repository", None)

        if interrupt_repo is not None:
            try:
                await interrupt_repo.create_interrupt(request)
            except Exception:
                logger.warning(
                    "interrupt_persist_failed",
                    run_id=run_id,
                    stage=stage,
                )

        # Publish event
        await self._publish_requested_event(request, configurable)

        # Send channel notification if configured
        if self.channel_config:
            try:
                from lintel.workflows.notifications.interrupt_notifier import (
                    send_interrupt_notification,
                )

                await send_interrupt_notification(request, self.channel_config, configurable)
            except Exception:
                logger.warning(
                    "interrupt_notification_failed",
                    run_id=run_id,
                    stage=stage,
                )

        # --- Pause the graph ---
        human_input = interrupt(request)

        # --- Resumed! ---
        await tracker.append_log(self.node_name, "Human input received, resuming")

        # Handle timeout sentinel
        if isinstance(human_input, TimeoutSentinel):
            return self._handle_timeout(state, human_input)

        # Delegate to subclass
        result = self.process_resume(state, human_input)

        # Publish resumed event
        await self._publish_resumed_event(request, human_input, configurable)

        # Mark stage completed
        await tracker.mark_completed(self.node_name, outputs=result)

        return result

    # --- Helpers ---

    def _build_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        """Build the interrupt payload from current state.

        Subclasses can override for custom payloads.
        """
        return {
            "node_name": self.node_name,
            "interrupt_type": self.interrupt_type.value,
            "current_phase": state.get("current_phase", ""),
        }

    def _handle_timeout(
        self,
        state: dict[str, Any],
        sentinel: TimeoutSentinel,
    ) -> dict[str, Any]:
        """Handle timeout based on the ``on_timeout`` policy."""
        if self.on_timeout == "auto_proceed":
            return {
                "current_phase": state.get("current_phase", ""),
                "agent_outputs": [
                    {
                        "node": self.node_name,
                        "output": f"Auto-proceeded after timeout: {sentinel.reason}",
                    }
                ],
            }
        # auto_escalate
        return {
            "current_phase": f"{self.node_name}_escalated",
            "error": f"Interrupt timed out ({sentinel.reason}), escalation required",
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": f"Escalated after timeout: {sentinel.reason}",
                }
            ],
        }

    async def _publish_requested_event(
        self,
        request: InterruptRequest,
        configurable: dict[str, Any],
    ) -> None:
        """Publish HumanInterruptRequested to the event store."""
        event_store = configurable.get("event_store")
        if event_store is None:
            app_state = configurable.get("app_state")
            if app_state is None and request.run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                app_state = get_app_state(request.run_id)
            if app_state is not None:
                event_store = getattr(app_state, "event_store", None)
        if event_store is None:
            return
        event = HumanInterruptRequested(
            payload={
                "interrupt_id": str(request.id),
                "run_id": request.run_id,
                "stage": request.stage,
                "interrupt_type": request.interrupt_type.value,
                "timeout_seconds": request.timeout_seconds,
                "deadline": request.deadline.isoformat() if request.deadline else None,
            },
        )
        try:
            await event_store.append(
                stream_id=f"run:{request.run_id}",
                events=[event],
            )
        except Exception:
            logger.warning("interrupt_event_publish_failed", run_id=request.run_id)

    async def _publish_resumed_event(
        self,
        request: InterruptRequest,
        human_input: Any,  # noqa: ANN401
        configurable: dict[str, Any],
    ) -> None:
        """Publish HumanInterruptResumed to the event store."""
        event_store = configurable.get("event_store")
        if event_store is None:
            app_state = configurable.get("app_state")
            if app_state is None and request.run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                app_state = get_app_state(request.run_id)
            if app_state is not None:
                event_store = getattr(app_state, "event_store", None)
        if event_store is None:
            return
        event = HumanInterruptResumed(
            payload={
                "interrupt_id": str(request.id),
                "run_id": request.run_id,
                "stage": request.stage,
                "interrupt_type": request.interrupt_type.value,
            },
        )
        try:
            await event_store.append(
                stream_id=f"run:{request.run_id}",
                events=[event],
            )
        except Exception:
            logger.warning("interrupt_resumed_event_publish_failed", run_id=request.run_id)
