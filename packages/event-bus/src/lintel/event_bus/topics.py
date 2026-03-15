"""Event topic constants for the Lintel event bus.

These string constants define the canonical topic names used when publishing
and subscribing to events. Using constants avoids typos and provides a
single source of truth for topic names.
"""

from __future__ import annotations

# Agent work queue lifecycle topics
AGENT_QUEUED = "agent.queued"
AGENT_SLOT_ACQUIRED = "agent.slot.acquired"
AGENT_SLOT_RELEASED = "agent.slot.released"
