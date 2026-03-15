"""Tests for event bus topic constants."""

from __future__ import annotations


class TestTopics:
    def test_agent_queued_topic(self) -> None:
        from lintel.event_bus.topics import AGENT_QUEUED

        assert AGENT_QUEUED == "agent.queued"

    def test_agent_slot_acquired_topic(self) -> None:
        from lintel.event_bus.topics import AGENT_SLOT_ACQUIRED

        assert AGENT_SLOT_ACQUIRED == "agent.slot.acquired"

    def test_agent_slot_released_topic(self) -> None:
        from lintel.event_bus.topics import AGENT_SLOT_RELEASED

        assert AGENT_SLOT_RELEASED == "agent.slot.released"

    def test_all_topics_exported_from_init(self) -> None:
        from lintel.event_bus import AGENT_QUEUED, AGENT_SLOT_ACQUIRED, AGENT_SLOT_RELEASED

        assert AGENT_QUEUED is not None
        assert AGENT_SLOT_ACQUIRED is not None
        assert AGENT_SLOT_RELEASED is not None
