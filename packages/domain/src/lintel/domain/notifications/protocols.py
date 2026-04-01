"""NotificationService protocol — cross-cutting notification dispatch interface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from lintel.domain.types import NotificationChannel


@runtime_checkable
class NotificationService(Protocol):
    """Sends a notification to a recipient via the specified channel."""

    async def notify(
        self,
        recipient: str,
        channel: NotificationChannel,
        template: str,
        context: dict[str, str],
    ) -> None: ...
