"""Channel type enumeration for multi-channel adapter support."""

from __future__ import annotations

from enum import StrEnum


class ChannelType(StrEnum):
    """Supported messaging channel types."""

    SLACK = "slack"
    TELEGRAM = "telegram"
