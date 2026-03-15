"""Generic channel adapter protocol for multi-channel messaging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef


@runtime_checkable
class ChannelAdapter(Protocol):
    """Protocol defining the interface all channel adapters must implement.

    Each adapter (Slack, Telegram, etc.) implements this protocol to provide
    a uniform interface for sending messages and approval requests.
    """

    async def send_message(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]: ...

    async def send_reply(
        self,
        thread_ref: ThreadRef,
        text: str,
        **kwargs: object,
    ) -> dict[str, Any]: ...

    async def send_approval_request(
        self,
        thread_ref: ThreadRef,
        gate_type: str,
        summary: str,
        callback_id: str,
    ) -> dict[str, Any]: ...
