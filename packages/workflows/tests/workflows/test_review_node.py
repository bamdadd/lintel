"""Tests for the review workflow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes.review import review_output


def _make_state(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_ref": "thread:W1:C1:ts1",
        "correlation_id": "run-1",
        "run_id": "run-1",
        "sandbox_id": "sbx-1",
        "workspace_path": "/workspace/repo",
        "sanitized_messages": ["test"],
        "agent_outputs": [],
        "sandbox_results": [],
    }
    base.update(overrides)
    return base


def _make_config(
    sandbox_manager: object = None,
    agent_runtime: object = None,
) -> dict[str, Any]:
    return {
        "configurable": {
            "sandbox_manager": sandbox_manager,
            "agent_runtime": agent_runtime,
            "pipeline_store": None,
        }
    }


async def test_review_reconnects_network_before_agent() -> None:
    """Review must reconnect network before running Claude Code."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="diff --git a/f.py\n+hello", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(
        return_value={
            "content": "VERDICT: APPROVE\nLooks good.",
        }
    )

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    await review_output(_make_state(), config)

    sandbox.reconnect_network.assert_called_once_with("sbx-1")
    sandbox.disconnect_network.assert_called_once_with("sbx-1")


async def test_review_disconnects_network_after_agent() -> None:
    """Review disconnects network after completion."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="diff --git a/f.py\n+hello", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(
        return_value={
            "content": "VERDICT: REQUEST_CHANGES\nFix the naming.",
        }
    )

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    sandbox.disconnect_network.assert_called_once_with("sbx-1")
    # Verdict should be request_changes
    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "request_changes"


async def test_review_marks_failed_on_request_changes() -> None:
    """Review with request_changes verdict marks stage as failed."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="diff --git a/f.py\n+hello", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(
        return_value={
            "content": "VERDICT: REQUEST_CHANGES\nNeeds work.",
        }
    )

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "request_changes"
    # current_phase should go back to implementing
    assert result["current_phase"] == "implementing"


async def test_review_approve_verdict() -> None:
    """Review with APPROVE verdict passes through."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="diff --git a/f.py\n+hello", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(
        return_value={
            "content": "VERDICT: APPROVE\nAll good.",
        }
    )

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "approve"
    assert result["current_phase"] == "awaiting_pr_approval"


async def test_review_no_diff_auto_approves() -> None:
    """Review with empty diff auto-approves."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    config = _make_config(sandbox_manager=sandbox)
    result = await review_output(_make_state(), config)

    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "approve"
