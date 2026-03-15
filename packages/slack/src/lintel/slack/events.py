"""Slack domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class ThreadMessageReceived(EventEnvelope):
    event_type: str = "ThreadMessageReceived"


register_events(
    ThreadMessageReceived,
)
