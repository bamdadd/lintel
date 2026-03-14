"""Tests for workflow notification helpers."""

from __future__ import annotations

from lintel.workflows.nodes._notifications import (
    extract_conversation_id,
    notify_phase_change,
)
import pytest


class TestExtractConversationId:
    """extract_conversation_id parses thread_ref strings."""

    def test_valid_chat_thread_ref(self) -> None:
        ref = "thread:lintel-chat:chat:abc123"
        assert extract_conversation_id(ref) == "abc123"

    def test_valid_chat_thread_ref_extra_colons(self) -> None:
        ref = "thread:lintel-chat:chat:abc:extra"
        assert extract_conversation_id(ref) == "abc"

    def test_slack_thread_ref_returns_none(self) -> None:
        ref = "thread:T12345:C67890:1234567890.123456"
        assert extract_conversation_id(ref) is None

    def test_empty_string_returns_none(self) -> None:
        assert extract_conversation_id("") is None

    def test_no_thread_prefix(self) -> None:
        ref = "lintel-chat:chat:abc123"
        assert extract_conversation_id(ref) == "abc123"

    def test_short_ref_returns_none(self) -> None:
        ref = "thread:lintel-chat:chat"
        assert extract_conversation_id(ref) is None


class TestNotifyPhaseChange:
    """notify_phase_change adds messages to the chat store."""

    @pytest.fixture()
    def memory_store(self) -> object:
        """Create an in-memory ChatStore."""
        from lintel.api.routes.chat import ChatStore

        return ChatStore()

    async def test_adds_message_to_store(self, memory_store: object) -> None:
        store = memory_store
        await store.create(
            conversation_id="conv1",
            user_id="u1",
            display_name=None,
            project_id=None,
        )

        await notify_phase_change(store, "conv1", "planning", "Generating plan")

        conv = await store.get("conv1")
        assert conv is not None
        assert len(conv["messages"]) == 1
        msg = conv["messages"][0]
        assert msg["role"] == "agent"
        assert "planning" in msg["content"]
        assert "Generating plan" in msg["content"]

    async def test_noop_when_store_is_none(self) -> None:
        # Should not raise
        await notify_phase_change(None, "conv1", "testing", "Running tests")

    async def test_missing_conversation_does_not_raise(self, memory_store: object) -> None:
        # conversation "missing" does not exist — should log warning, not raise
        await notify_phase_change(memory_store, "missing", "testing", "Running tests")
