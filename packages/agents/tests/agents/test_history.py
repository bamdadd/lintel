"""Tests for message history management (sliding window + summarisation)."""

from __future__ import annotations

from typing import Any

from lintel.agents.history import (
    HistoryConfig,
    MessageHistoryManager,
    _estimate_tokens,
    _format_messages_for_summary,
)


def _msg(role: str, content: str) -> dict[str, Any]:
    return {"role": role, "content": content}


class TestEstimateTokens:
    def test_empty(self) -> None:
        assert _estimate_tokens([]) == 0

    def test_single_message(self) -> None:
        # 20 chars -> 5 tokens (20 // 4)
        assert _estimate_tokens([_msg("user", "a" * 20)]) == 5


class TestFormatMessages:
    def test_formats_with_roles(self) -> None:
        msgs = [_msg("user", "hello"), _msg("assistant", "hi")]
        result = _format_messages_for_summary(msgs)
        assert "[user] hello" in result
        assert "[assistant] hi" in result


class TestMessageHistoryManagerNoSummary:
    """Tests for sliding window without a summarisation callback."""

    async def test_short_conversation_unchanged(self) -> None:
        msgs = [_msg("system", "sys"), _msg("user", "hi"), _msg("assistant", "hello")]
        manager = MessageHistoryManager(config=HistoryConfig(max_window=20))
        result = await manager.apply(msgs)
        assert result.messages == msgs
        assert result.evicted_count == 0
        assert result.summary_added is False

    async def test_empty_messages(self) -> None:
        manager = MessageHistoryManager()
        result = await manager.apply([])
        assert result.messages == []
        assert result.evicted_count == 0

    async def test_window_evicts_old_messages(self) -> None:
        system = _msg("system", "You are helpful.")
        # max_window=5 means 1 system + 4 conversation msgs kept
        conversation = [_msg("user", f"msg {i}") for i in range(10)]
        manager = MessageHistoryManager(config=HistoryConfig(max_window=5))
        result = await manager.apply([system, *conversation])

        # Should have system + notice + 4 recent messages = 6 total
        assert result.evicted_count == 6
        # The last 4 conversation messages should be the most recent ones
        kept_contents = [m["content"] for m in result.messages if m["role"] == "user"]
        assert kept_contents == ["msg 6", "msg 7", "msg 8", "msg 9"]

    async def test_eviction_adds_truncation_notice(self) -> None:
        """When evicted messages are long enough, a truncation notice is added."""
        system = _msg("system", "sys")
        # Create messages long enough to exceed _MIN_EVICTION_CHARS (200)
        long_msg = "x" * 300
        conversation = [_msg("user", long_msg)] * 6
        manager = MessageHistoryManager(config=HistoryConfig(max_window=3))
        result = await manager.apply([system, *conversation])
        assert result.summary_added is True
        # Find the summary message
        summaries = [
            m for m in result.messages if "trimmed from this conversation" in m.get("content", "")
        ]
        assert len(summaries) == 1

    async def test_short_eviction_no_notice(self) -> None:
        """When evicted messages are very short, no summary/notice is added."""
        system = _msg("system", "s")
        conversation = [_msg("user", "hi")] * 6
        manager = MessageHistoryManager(config=HistoryConfig(max_window=3))
        result = await manager.apply([system, *conversation])
        assert result.evicted_count == 4
        # Short evictions don't produce a notice
        assert result.summary_added is False


class TestMessageHistoryManagerWithSummary:
    """Tests for sliding window with a summarisation callback."""

    async def test_summary_callback_invoked(self) -> None:
        called_with: list[str] = []

        async def mock_summarise(text: str) -> str:
            called_with.append(text)
            return "Summary of earlier conversation."

        system = _msg("system", "sys")
        long_msg = "x" * 300
        conversation = [_msg("user", long_msg)] * 6
        manager = MessageHistoryManager(
            config=HistoryConfig(max_window=3),
            summary_callback=mock_summarise,
        )
        result = await manager.apply([system, *conversation])

        assert len(called_with) == 1
        assert result.summary_added is True
        # The summary message should contain our callback's output
        summary_msgs = [
            m for m in result.messages if "Summary of earlier conversation" in m.get("content", "")
        ]
        assert len(summary_msgs) == 1
        assert summary_msgs[0]["role"] == "system"

    async def test_summary_callback_failure_graceful(self) -> None:
        """If the summary callback raises, we still get a valid result."""

        async def failing_summarise(text: str) -> str:
            msg = "LLM error"
            raise RuntimeError(msg)

        system = _msg("system", "sys")
        long_msg = "x" * 300
        conversation = [_msg("user", long_msg)] * 6
        manager = MessageHistoryManager(
            config=HistoryConfig(max_window=3),
            summary_callback=failing_summarise,
        )
        result = await manager.apply([system, *conversation])

        # Should not crash; eviction still happens
        assert result.evicted_count == 4
        # No summary added since callback failed
        assert result.summary_added is False


class TestHistoryConfigTokenBudget:
    async def test_token_budget_trims_kept_messages(self) -> None:
        system = _msg("system", "s")
        # Each message ~100 tokens (400 chars)
        big = "x" * 400
        conversation = [_msg("user", big)] * 10
        manager = MessageHistoryManager(
            config=HistoryConfig(max_window=8, max_total_tokens=300),
        )
        result = await manager.apply([system, *conversation])
        # With a 300 token budget, only a few messages fit
        assert result.estimated_tokens <= 300 + 50  # some slack for system msg


class TestPreserveSystemFalse:
    async def test_no_system_preservation(self) -> None:
        msgs = [_msg("system", "sys"), _msg("user", "a")] * 5
        manager = MessageHistoryManager(
            config=HistoryConfig(max_window=3, preserve_system=False),
        )
        result = await manager.apply(msgs)
        # With preserve_system=False, system msgs are treated like any other
        assert result.evicted_count > 0
