"""Channel router engine for resolving messages to workflow definitions."""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.channel_message_routing_api.store import RoutingRule


class ChannelRouter:
    """Routes incoming messages to workflows based on connection-scoped rules."""

    def resolve(
        self,
        rules: list[RoutingRule],
        connection_id: str,
        channel: str,
        message: str,
    ) -> RoutingRule | None:
        """Find the highest-priority matching rule for a message."""
        candidates = [
            r
            for r in rules
            if r.enabled
            and r.connection_id == connection_id
            and fnmatch.fnmatch(channel, r.channel_pattern)
            and (not r.message_pattern or r.message_pattern in message)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda r: r.priority, reverse=True)
        return candidates[0]
