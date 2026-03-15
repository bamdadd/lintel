"""Slack protocol definitions.

The ChannelAdapter protocol has moved to lintel.contracts.channel_adapter.
This module re-exports it for backward compatibility.
"""

from __future__ import annotations

from lintel.contracts.channel_adapter import ChannelAdapter

__all__ = ["ChannelAdapter"]
