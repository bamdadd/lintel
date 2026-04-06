"""Tests for the review workflow node."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from structlog.testing import capture_logs

from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes.review import _parse_findings, review_output


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


def _sandbox_with_diff(diff: str = "diff --git a/f.py\n+hello") -> AsyncMock:
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout=diff, stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()
    return sandbox


def _runtime_with_content(content: str) -> AsyncMock:
    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(return_value={"content": content})
    return runtime


async def test_review_reconnects_network_before_agent() -> None:
    """Review must reconnect network before running Claude Code."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nLooks good.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    await review_output(_make_state(), config)

    sandbox.reconnect_network.assert_called_once_with("sbx-1")
    sandbox.disconnect_network.assert_called_once_with("sbx-1")


async def test_review_disconnects_network_after_agent() -> None:
    """Review disconnects network after completion."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: REQUEST_CHANGES\nFix the naming.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    sandbox.disconnect_network.assert_called_once_with("sbx-1")
    # Verdict should be request_changes
    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "request_changes"


async def test_review_marks_failed_on_request_changes() -> None:
    """Review with request_changes verdict marks stage as failed."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: REQUEST_CHANGES\nNeeds work.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    outputs = result.get("agent_outputs", [])
    assert outputs[0]["verdict"] == "request_changes"
    # current_phase should go back to implementing
    assert result["current_phase"] == "implementing"


async def test_review_approve_verdict() -> None:
    """Review with APPROVE verdict passes through."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nAll good.")

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


# --- New tests for structured logging, state fields, and audit ---


async def test_review_returns_review_decision_field() -> None:
    """Review node populates review_decision in the return dict."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nAll good.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    assert result["review_decision"] == "approve"


async def test_review_returns_review_decision_request_changes() -> None:
    """Review node sets review_decision to request_changes."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: REQUEST_CHANGES\n- Bug in auth logic.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    assert result["review_decision"] == "request_changes"


async def test_review_returns_findings() -> None:
    """Review node extracts findings from review text."""
    sandbox = _sandbox_with_diff()
    review_text = (
        "VERDICT: REQUEST_CHANGES\n"
        "Summary: Two issues found.\n"
        "1. SQL injection in user input handler\n"
        "2. Missing null check on response object\n"
        "- Also consider adding type hints\n"
    )
    runtime = _runtime_with_content(review_text)

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    assert result["review_decision"] == "request_changes"
    assert len(result["review_findings"]) == 3
    assert "SQL injection" in result["review_findings"][0]


async def test_review_no_diff_returns_empty_findings() -> None:
    """Review with no diff returns empty findings list."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="", stderr=""),
    )
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    config = _make_config(sandbox_manager=sandbox)
    result = await review_output(_make_state(), config)

    assert result["review_decision"] == "approve"
    assert result["review_findings"] == []


async def test_review_emits_structlog() -> None:
    """Review node emits structured log entries via structlog."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nLooks good.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)

    with capture_logs() as cap_logs:
        await review_output(_make_state(), config)

    # Find the review_completed log entry
    completed_logs = [e for e in cap_logs if e.get("event") == "review_completed"]
    assert len(completed_logs) == 1
    assert completed_logs[0]["verdict"] == "approve"
    assert completed_logs[0]["run_id"] == "run-1"
    assert "finding_count" in completed_logs[0]


async def test_review_emits_structlog_on_request_changes() -> None:
    """Structured log captures request_changes verdict."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: REQUEST_CHANGES\n- Fix auth.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)

    with capture_logs() as cap_logs:
        await review_output(_make_state(), config)

    completed_logs = [e for e in cap_logs if e.get("event") == "review_completed"]
    assert len(completed_logs) == 1
    assert completed_logs[0]["verdict"] == "request_changes"


async def test_review_emits_audit_entry() -> None:
    """Review node emits audit entry when audit store is available."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nAll good.")

    # Provide an app_state with an audit_entry_store
    audit_store = AsyncMock()
    audit_store.add = AsyncMock()

    class _FakeAppState:
        audit_entry_store = audit_store

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "agent_runtime": runtime,
            "pipeline_store": None,
            "app_state": _FakeAppState(),
        }
    }
    await review_output(_make_state(), config)

    audit_store.add.assert_called_once()
    entry = audit_store.add.call_args[0][0]
    assert entry.action == "review_completed"
    assert entry.resource_id == "run-1"
    assert entry.details is not None
    assert entry.details["verdict"] == "approve"


async def test_review_increments_review_cycles() -> None:
    """Review node increments review_cycles counter."""
    sandbox = _sandbox_with_diff()
    runtime = _runtime_with_content("VERDICT: APPROVE\nLooks good.")

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(review_cycles=2), config)

    assert result["review_cycles"] == 3


async def test_review_agent_exception_propagates_output() -> None:
    """When the agent raises, review still produces output (fallback text)."""
    sandbox = _sandbox_with_diff()
    runtime = AsyncMock()
    runtime.execute_step_stream = AsyncMock(side_effect=RuntimeError("LLM down"))

    config = _make_config(sandbox_manager=sandbox, agent_runtime=runtime)
    result = await review_output(_make_state(), config)

    # Should default to approve with fallback message
    assert result["review_decision"] == "approve"
    assert "Agent review failed" in result["agent_outputs"][0]["output"]


# --- Unit tests for _parse_findings ---


def test_parse_findings_numbered() -> None:
    """Parse numbered findings."""
    text = "1. Bug in handler\n2. Missing check\nSome other text"
    assert _parse_findings(text) == ["1. Bug in handler", "2. Missing check"]


def test_parse_findings_bullets() -> None:
    """Parse bullet-point findings."""
    text = "- First issue\n* Second issue\nNon-issue line"
    assert _parse_findings(text) == ["- First issue", "* Second issue"]


def test_parse_findings_skips_verdict() -> None:
    """VERDICT lines are not included as findings."""
    text = "- VERDICT: APPROVE\n- Real finding here"
    assert _parse_findings(text) == ["- Real finding here"]


def test_parse_findings_empty() -> None:
    """No findings in plain text."""
    text = "Looks good overall. No issues found."
    assert _parse_findings(text) == []
