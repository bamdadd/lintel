"""Tests for PipelineStageNotifier."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.contracts.channel_type import ChannelType
from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ThreadRef
from lintel.slack.stage_notifier import (
    STAGE_EVENT_TYPES,
    PipelineStageNotifier,
    _status_from_event_type,
)


def _make_thread_ref() -> ThreadRef:
    return ThreadRef(
        workspace_id="T111",
        channel_id="C999",
        thread_ts="1234567890.000",
        channel_type=ChannelType.SLACK,
    )


def _make_event(event_type: str, payload: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope(event_type=event_type, payload=payload)


class _FakeLookup:
    def __init__(self, thread_ref: ThreadRef | None = None) -> None:
        self._ref = thread_ref

    async def get_thread_ref(self, run_id: str) -> ThreadRef | None:
        return self._ref


class TestPipelineStageNotifier:
    async def test_posts_to_slack_thread_on_stage_completed(self) -> None:
        adapter = AsyncMock()
        adapter.send_message.return_value = {}
        ref = _make_thread_ref()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(ref))

        event = _make_event(
            "PipelineStageCompleted",
            {"run_id": "run-1", "node_name": "implement", "timestamp_ms": 5000},
        )
        await notifier.handle(event)

        adapter.send_message.assert_called_once()
        call_args = adapter.send_message.call_args
        assert call_args[0][0] == ref
        assert "implement" in call_args[0][1]
        assert call_args[1]["blocks"] is not None

    async def test_skips_when_no_run_id(self) -> None:
        adapter = AsyncMock()
        notifier = PipelineStageNotifier(
            adapter=adapter, run_lookup=_FakeLookup(_make_thread_ref())
        )
        event = _make_event("PipelineStageCompleted", {})
        await notifier.handle(event)
        adapter.send_message.assert_not_called()

    async def test_skips_when_no_thread_ref(self) -> None:
        adapter = AsyncMock()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(None))
        event = _make_event("PipelineStageCompleted", {"run_id": "run-1"})
        await notifier.handle(event)
        adapter.send_message.assert_not_called()

    async def test_handles_adapter_failure_gracefully(self) -> None:
        adapter = AsyncMock()
        adapter.send_message.side_effect = RuntimeError("Slack API down")
        ref = _make_thread_ref()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(ref))

        event = _make_event("PipelineStageCompleted", {"run_id": "run-1", "node_name": "review"})
        # Should not raise
        await notifier.handle(event)

    async def test_includes_error_in_failed_stage(self) -> None:
        adapter = AsyncMock()
        adapter.send_message.return_value = {}
        ref = _make_thread_ref()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(ref))

        event = _make_event(
            "PipelineStageTimedOut",
            {"run_id": "run-1", "node_name": "implement", "error": "Timeout after 300s"},
        )
        await notifier.handle(event)

        blocks = adapter.send_message.call_args[1]["blocks"]
        block_texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("Timeout" in t for t in block_texts)

    async def test_pipeline_run_started_posts_running(self) -> None:
        adapter = AsyncMock()
        adapter.send_message.return_value = {}
        ref = _make_thread_ref()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(ref))

        event = _make_event(
            "PipelineRunStarted",
            {"run_id": "run-1", "node_name": "pipeline"},
        )
        await notifier.handle(event)
        adapter.send_message.assert_called_once()

    async def test_pipeline_run_failed_posts_failed(self) -> None:
        adapter = AsyncMock()
        adapter.send_message.return_value = {}
        ref = _make_thread_ref()
        notifier = PipelineStageNotifier(adapter=adapter, run_lookup=_FakeLookup(ref))

        event = _make_event(
            "PipelineRunFailed",
            {"run_id": "run-1", "error": "Sandbox crashed"},
        )
        await notifier.handle(event)
        blocks = adapter.send_message.call_args[1]["blocks"]
        block_texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("Sandbox crashed" in t for t in block_texts)


class TestStatusMapping:
    def test_all_stage_event_types_have_mappings(self) -> None:
        for et in STAGE_EVENT_TYPES:
            status = _status_from_event_type(et)
            assert status != "unknown", f"{et} has no status mapping"

    def test_completed_maps_to_succeeded(self) -> None:
        assert _status_from_event_type("PipelineStageCompleted") == "succeeded"

    def test_timed_out_maps_correctly(self) -> None:
        assert _status_from_event_type("PipelineStageTimedOut") == "timed_out"

    def test_unknown_event_returns_unknown(self) -> None:
        assert _status_from_event_type("SomeRandomEvent") == "unknown"
