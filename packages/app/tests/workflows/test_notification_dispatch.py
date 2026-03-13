"""Tests for notification rule dispatch in stage tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

from lintel.workflows.nodes._stage_tracking import _pattern_matches, mark_completed


class TestPatternMatches:
    def test_exact_match(self) -> None:
        assert _pattern_matches("research.succeeded", "research.succeeded")

    def test_wildcard_all(self) -> None:
        assert _pattern_matches("*", "research.succeeded")

    def test_empty_pattern(self) -> None:
        assert _pattern_matches("", "research.succeeded")

    def test_wildcard_status(self) -> None:
        assert _pattern_matches("*.succeeded", "research.succeeded")
        assert _pattern_matches("*.succeeded", "plan.succeeded")
        assert not _pattern_matches("*.succeeded", "research.failed")

    def test_wildcard_stage(self) -> None:
        assert _pattern_matches("research.*", "research.succeeded")
        assert _pattern_matches("research.*", "research.failed")
        assert not _pattern_matches("plan.*", "research.succeeded")

    def test_no_match(self) -> None:
        assert not _pattern_matches("plan.failed", "research.succeeded")


@dataclass
class FakeRule:
    rule_id: str = "r1"
    event_pattern: str = "*.succeeded"
    channel: str = "slack"
    target: str = "C12345"
    enabled: bool = True
    project_id: str = ""


class TestNotificationDispatch:
    async def test_matching_rule_sends_slack(self) -> None:
        """When a stage completes and a rule matches, send a Slack message."""
        channel_adapter = AsyncMock()
        notification_rule_store = AsyncMock()
        notification_rule_store.list_all.return_value = [FakeRule()]
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None  # stage tracking will handle

        app_state = AsyncMock()
        app_state.notification_rule_store = notification_rule_store
        app_state.channel_adapter = channel_adapter
        app_state.pipeline_store = pipeline_store

        config: dict[str, Any] = {
            "configurable": {
                "app_state": app_state,
                "pipeline_store": pipeline_store,
            },
        }

        await mark_completed(config, "research", state={"run_id": "run-1"})

        channel_adapter.send_message.assert_called_once()
        call_kwargs = channel_adapter.send_message.call_args.kwargs
        assert call_kwargs["channel_id"] == "C12345"
        assert "research" in call_kwargs["text"]

    async def test_disabled_rule_skipped(self) -> None:
        """Disabled rules should not trigger notifications."""
        channel_adapter = AsyncMock()
        notification_rule_store = AsyncMock()
        notification_rule_store.list_all.return_value = [
            FakeRule(enabled=False),
        ]
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        app_state = AsyncMock()
        app_state.notification_rule_store = notification_rule_store
        app_state.channel_adapter = channel_adapter
        app_state.pipeline_store = pipeline_store

        config: dict[str, Any] = {
            "configurable": {
                "app_state": app_state,
                "pipeline_store": pipeline_store,
            },
        }

        await mark_completed(config, "research", state={"run_id": "run-1"})

        channel_adapter.send_message.assert_not_called()

    async def test_non_matching_pattern_skipped(self) -> None:
        """Rules that don't match the event pattern should not trigger."""
        channel_adapter = AsyncMock()
        notification_rule_store = AsyncMock()
        notification_rule_store.list_all.return_value = [
            FakeRule(event_pattern="plan.failed"),
        ]
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        app_state = AsyncMock()
        app_state.notification_rule_store = notification_rule_store
        app_state.channel_adapter = channel_adapter
        app_state.pipeline_store = pipeline_store

        config: dict[str, Any] = {
            "configurable": {
                "app_state": app_state,
                "pipeline_store": pipeline_store,
            },
        }

        await mark_completed(config, "research", state={"run_id": "run-1"})

        channel_adapter.send_message.assert_not_called()
