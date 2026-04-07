"""Tests for the self-review quality loop (_self_review module)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes._self_review import (
    MAX_SELF_REVIEW_ITERATIONS,
    _extract_verdict,
    run_self_review_loop,
)

# ---------------------------------------------------------------------------
# _extract_verdict
# ---------------------------------------------------------------------------


class TestExtractVerdict:
    def test_roadhouse_verdict(self) -> None:
        assert _extract_verdict("Great work! <verdict>roadhouse!</verdict>") == "roadhouse!"

    def test_needs_work_verdict(self) -> None:
        assert _extract_verdict("Issues found. <verdict>needs-work</verdict>") == "needs-work"

    def test_missing_tag_defaults_to_needs_work(self) -> None:
        assert _extract_verdict("No verdict tag here") == "needs-work"

    def test_case_insensitive(self) -> None:
        assert _extract_verdict("<Verdict>Roadhouse!</Verdict>") == "roadhouse!"
        assert _extract_verdict("<VERDICT>NEEDS-WORK</VERDICT>") == "needs-work"

    def test_whitespace_in_tag(self) -> None:
        assert _extract_verdict("<verdict>  roadhouse!  </verdict>") == "roadhouse!"
        assert _extract_verdict("<verdict> needs-work </verdict>") == "needs-work"

    def test_roadhouse_without_exclamation(self) -> None:
        assert _extract_verdict("<verdict>roadhouse</verdict>") == "roadhouse!"

    def test_empty_tag(self) -> None:
        assert _extract_verdict("<verdict></verdict>") == "needs-work"

    def test_multiple_tags_uses_first(self) -> None:
        text = "<verdict>roadhouse!</verdict> later <verdict>needs-work</verdict>"
        assert _extract_verdict(text) == "roadhouse!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sandbox_manager() -> AsyncMock:
    """Return a mock SandboxManager with execute returning a diff."""
    mgr = AsyncMock()
    result = MagicMock()
    result.stdout = "diff --git a/foo.py b/foo.py\n+hello"
    result.stderr = ""
    result.exit_code = 0
    mgr.execute.return_value = result
    return mgr


def _make_agent_runtime(*responses: str) -> AsyncMock:
    """Return a mock AgentRuntime whose execute_step returns the given responses in order."""
    rt = AsyncMock()
    side_effects = [{"content": r, "usage": {}} for r in responses]
    rt.execute_step.side_effect = side_effects
    return rt


def _make_state() -> dict[str, Any]:
    return {"run_id": "test-run", "stages": {}}


def _make_config() -> dict[str, Any]:
    return {"configurable": {}}


# ---------------------------------------------------------------------------
# run_self_review_loop
# ---------------------------------------------------------------------------


class TestRunSelfReviewLoop:
    async def test_exits_after_one_iteration_when_both_pass(self) -> None:
        rt = _make_agent_runtime(
            "Looks good! <verdict>roadhouse!</verdict>",
            "Excellent! <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()
        usage: list[dict[str, Any]] = []

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=usage,
        )

        # 2 review calls (proud + world-class), no fix call
        assert rt.execute_step.call_count == 2
        assert len(usage) == 2

    async def test_retries_when_proud_check_fails(self) -> None:
        rt = _make_agent_runtime(
            # Iteration 1: proud fails, world-class passes
            "Issues! <verdict>needs-work</verdict>",
            "Good! <verdict>roadhouse!</verdict>",
            "Fixing...",  # fix step
            # Iteration 2: both pass
            "Nice! <verdict>roadhouse!</verdict>",
            "World class! <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()
        usage: list[dict[str, Any]] = []

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=usage,
        )

        # iter1: proud + wc + fix = 3, iter2: proud + wc = 2
        assert rt.execute_step.call_count == 5
        assert len(usage) == 5

    async def test_retries_when_world_class_check_fails(self) -> None:
        rt = _make_agent_runtime(
            # Iteration 1: proud passes, world-class fails
            "Good! <verdict>roadhouse!</verdict>",
            "Not great. <verdict>needs-work</verdict>",
            "Fixing...",  # fix step
            # Iteration 2: both pass
            "Good! <verdict>roadhouse!</verdict>",
            "Excellent! <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()
        usage: list[dict[str, Any]] = []

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=usage,
        )

        assert rt.execute_step.call_count == 5

    async def test_exhausts_after_max_iterations(self) -> None:
        # Every iteration: both fail → fix → repeat until exhausted
        responses: list[str] = []
        for _i in range(MAX_SELF_REVIEW_ITERATIONS):
            responses.append("Bad. <verdict>needs-work</verdict>")  # proud
            responses.append("Bad. <verdict>needs-work</verdict>")  # world-class
            if _i < MAX_SELF_REVIEW_ITERATIONS - 1:
                responses.append("Trying to fix...")  # fix (not on last iter)

        rt = _make_agent_runtime(*responses)
        mgr = _make_sandbox_manager()
        usage: list[dict[str, Any]] = []

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=usage,
        )

        # Each iteration: 2 reviews + 1 fix (except last: 2 reviews only)
        expected_calls = (MAX_SELF_REVIEW_ITERATIONS * 2) + (MAX_SELF_REVIEW_ITERATIONS - 1)
        assert rt.execute_step.call_count == expected_calls

    async def test_prompts_include_diff_context(self) -> None:
        rt = _make_agent_runtime(
            "OK <verdict>roadhouse!</verdict>",
            "OK <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=[],
        )

        # Both review calls should include the diff in the user message
        for call in rt.execute_step.call_args_list:
            messages = call.kwargs["messages"]
            user_msg = messages[-1]["content"]
            assert "diff --git" in user_msg

    async def test_proud_prompt_sent_correctly(self) -> None:
        rt = _make_agent_runtime(
            "OK <verdict>roadhouse!</verdict>",
            "OK <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=[],
        )

        proud_call = rt.execute_step.call_args_list[0]
        proud_user_msg = proud_call.kwargs["messages"][-1]["content"]
        assert "Are you proud" in proud_user_msg

    async def test_world_class_prompt_sent_correctly(self) -> None:
        rt = _make_agent_runtime(
            "OK <verdict>roadhouse!</verdict>",
            "OK <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=[],
        )

        wc_call = rt.execute_step.call_args_list[1]
        wc_user_msg = wc_call.kwargs["messages"][-1]["content"]
        assert "world class" in wc_user_msg

    async def test_token_usage_accumulated(self) -> None:
        rt = _make_agent_runtime(
            "OK <verdict>roadhouse!</verdict>",
            "OK <verdict>roadhouse!</verdict>",
        )
        mgr = _make_sandbox_manager()
        usage: list[dict[str, Any]] = [{"existing": True}]

        await run_self_review_loop(
            agent_runtime=rt,
            thread_ref=("ws", "ch", "ts"),
            sandbox_manager=mgr,
            sandbox_id="sbx",
            workspace_path="/repo",
            config=_make_config(),
            state=_make_state(),
            total_usage=usage,
        )

        # Original entry + 2 review entries
        assert len(usage) == 3
