"""In-memory store for Slack invocations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import SlackInvocation


def _invocation_to_dict(inv: SlackInvocation) -> dict[str, Any]:
    """Convert a SlackInvocation dataclass to a JSON-friendly dict."""
    d = asdict(inv)
    d["created_at"] = inv.created_at.isoformat()
    d["updated_at"] = inv.updated_at.isoformat()
    # Convert tuple of dicts to list for JSON serialisation
    d["thread_context"] = list(inv.thread_context)
    d["linked_urls"] = list(inv.linked_urls)
    return d


class InMemorySlackInvocationStore:
    """Simple in-memory store for Slack invocations."""

    def __init__(self) -> None:
        self._items: dict[str, SlackInvocation] = {}

    async def get(self, invocation_id: str) -> dict[str, Any] | None:
        inv = self._items.get(invocation_id)
        if inv is None:
            return None
        return _invocation_to_dict(inv)

    async def list_all(
        self,
        *,
        status: str | None = None,
        channel: str | None = None,
    ) -> list[dict[str, Any]]:
        results = list(self._items.values())
        if status is not None:
            results = [i for i in results if i.status == status]
        if channel is not None:
            results = [i for i in results if i.slack_channel_id == channel]
        return [_invocation_to_dict(i) for i in results]

    async def add(self, invocation: SlackInvocation) -> dict[str, Any]:
        self._items[invocation.invocation_id] = invocation
        return _invocation_to_dict(invocation)

    async def update(
        self,
        invocation_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        inv = self._items.get(invocation_id)
        if inv is None:
            return None
        data = asdict(inv)
        data.update(updates)
        updated = SlackInvocation(**data)
        self._items[invocation_id] = updated
        return _invocation_to_dict(updated)

    async def remove(self, invocation_id: str) -> bool:
        if invocation_id not in self._items:
            return False
        del self._items[invocation_id]
        return True
