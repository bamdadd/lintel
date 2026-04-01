"""Base class for event-driven projections with position tracking."""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope

logger = structlog.get_logger()

# Pre-compiled regex for CamelCase → snake_case conversion
_CAMEL_RE1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE2 = re.compile(r"([a-z0-9])([A-Z])")


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = _CAMEL_RE1.sub(r"\1_\2", name)
    return _CAMEL_RE2.sub(r"\1_\2", s1).lower()


class ProjectionBase(ABC):
    """Abstract base class for projections that dispatch events to typed handlers.

    Subclasses define ``on_<snake_case_event_type>`` methods.  For example,
    an event with ``event_type="ThreadMessageReceived"`` is dispatched to
    ``on_thread_message_received(envelope)``.

    Position tracking is built in: ``last_position`` is updated after each
    successful dispatch so catch-up subscriptions can resume from the correct
    point.

    Events with no matching handler are silently ignored.
    """

    def __init__(self) -> None:
        self.last_position: int = 0

    @abstractmethod
    def get_name(self) -> str:
        """Return a unique name for this projection (used as subscriber_id)."""

    async def handle(self, envelope: EventEnvelope) -> None:
        """Dispatch an event to the matching ``on_*`` handler method.

        Updates ``last_position`` after successful processing.
        """
        method_name = f"on_{_to_snake_case(envelope.event_type)}"
        handler = getattr(self, method_name, None)
        if handler is not None:
            await handler(envelope)
        else:
            logger.debug(
                "projection_no_handler",
                projection=self.get_name(),
                event_type=envelope.event_type,
                method=method_name,
            )
        position = envelope.global_position
        if position is not None:
            self.last_position = position
        await self.save_position(self.last_position)

    async def save_position(self, position: int) -> None:  # noqa: B027
        """Hook for subclasses to persist position to subscriber_positions table.

        Default implementation is a no-op.
        """
