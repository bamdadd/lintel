"""Tests for LLMCostTracker — context propagation and cost record creation."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from lintel.infrastructure.models.cost_tracker import (
    CostRecord,
    LLMCostTracker,
    clear_cost_context,
    get_cost_context,
    set_cost_context,
)


class TestCostContext:
    """Context variable management."""

    def test_set_and_get_context(self) -> None:
        set_cost_context(
            run_id="run-1",
            stage="implement",
            agent_role="coder",
            project_id="proj-1",
        )
        ctx = get_cost_context()
        assert ctx["run_id"] == "run-1"
        assert ctx["stage"] == "implement"
        assert ctx["agent_role"] == "coder"
        assert ctx["project_id"] == "proj-1"

    def test_clear_context(self) -> None:
        set_cost_context(run_id="run-1", agent_role="coder")
        clear_cost_context()
        ctx = get_cost_context()
        assert ctx["run_id"] == ""
        assert ctx["agent_role"] == ""

    def test_default_context_is_empty(self) -> None:
        clear_cost_context()
        ctx = get_cost_context()
        assert all(v == "" for v in ctx.values())


class TestLLMCostTracker:
    """LLMCostTracker.record_call and timer."""

    def test_start_timer_returns_monotonic(self) -> None:
        tracker = LLMCostTracker()
        t1 = tracker.start_timer()
        t2 = tracker.start_timer()
        assert t2 >= t1

    def test_record_call_extracts_tokens(self) -> None:
        tracker = LLMCostTracker()
        clear_cost_context()
        set_cost_context(run_id="run-1", stage="research", agent_role="coder", project_id="p1")

        response = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        response.model = "gpt-4"

        start = time.monotonic() - 0.1  # simulate 100ms elapsed

        with patch("litellm.completion_cost", return_value=0.0045):
            record = tracker.record_call(response, start)

        assert isinstance(record, CostRecord)
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.model == "gpt-4"
        assert record.cost_usd == 0.0045
        assert record.duration_ms >= 90  # at least ~100ms
        assert record.run_id == "run-1"
        assert record.stage == "research"
        assert record.agent_role == "coder"
        assert record.project_id == "p1"

        clear_cost_context()

    def test_record_call_handles_missing_usage(self) -> None:
        tracker = LLMCostTracker()
        clear_cost_context()

        response = MagicMock(spec=[])  # no attributes
        start = time.monotonic()

        with patch("litellm.completion_cost", side_effect=Exception("no cost")):
            record = tracker.record_call(response, start, model_override="test-model")

        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.cost_usd == 0.0
        assert record.model == "test-model"

    def test_record_call_litellm_cost_failure_returns_zero(self) -> None:
        tracker = LLMCostTracker()
        clear_cost_context()

        response = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5
        response.model = "unknown-model"

        with patch("litellm.completion_cost", side_effect=Exception("unknown model")):
            record = tracker.record_call(response, time.monotonic())

        assert record.cost_usd == 0.0
        assert record.input_tokens == 10

    def test_build_event_payload(self) -> None:
        tracker = LLMCostTracker()
        record = CostRecord(
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.005,
            duration_ms=150,
            run_id="run-1",
            stage="implement",
            agent_role="coder",
            project_id="proj-1",
        )
        payload = tracker.build_event_payload(record, provider="openai", tool_iterations=2)

        assert payload["model"] == "gpt-4"
        assert payload["input_tokens"] == 100
        assert payload["output_tokens"] == 50
        assert payload["cost_usd"] == 0.005
        assert payload["duration_ms"] == 150
        assert payload["agent_role"] == "coder"
        assert payload["run_id"] == "run-1"
        assert payload["stage"] == "implement"
        assert payload["project_id"] == "proj-1"
        assert payload["provider"] == "openai"
        assert payload["tool_iterations"] == 2

    def test_build_event_payload_omits_empty_optional_fields(self) -> None:
        tracker = LLMCostTracker()
        record = CostRecord(
            model="gpt-4",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            duration_ms=50,
            run_id="",
            stage="",
            agent_role="coder",
            project_id="",
        )
        payload = tracker.build_event_payload(record)
        assert "run_id" not in payload
        assert "stage" not in payload
        assert "project_id" not in payload
        assert payload["agent_role"] == "coder"

    def test_duration_computation(self) -> None:
        tracker = LLMCostTracker()
        clear_cost_context()

        response = MagicMock()
        response.usage.prompt_tokens = 1
        response.usage.completion_tokens = 1
        response.model = "m"

        start = time.monotonic() - 0.25  # 250ms ago

        with patch("litellm.completion_cost", return_value=0.0):
            record = tracker.record_call(response, start)

        # Should be roughly 250ms (allow some tolerance)
        assert record.duration_ms >= 200
        assert record.duration_ms < 500
