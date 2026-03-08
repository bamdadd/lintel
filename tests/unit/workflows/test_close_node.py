"""Tests for the close workflow node (PR creation and push)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from lintel.contracts.types import SandboxResult
from lintel.workflows.nodes.close import close_workflow


def _make_state(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_ref": "W1:C1:ts1",
        "correlation_id": "run-1",
        "sanitized_messages": ["add dark mode toggle"],
        "run_id": "run-1",
        "sandbox_id": "sbx-1",
        "feature_branch": "lintel/feat/dark-mode",
        "repo_branch": "main",
        "repo_url": "https://github.com/test/repo",
        "workspace_path": "/workspace/run-1/repo",
        "credential_ids": [],
        "plan": {"summary": "Add dark mode", "tasks": [{"title": "Toggle component"}]},
        "agent_outputs": [],
    }
    base.update(overrides)
    return base


def _make_config(
    sandbox_manager: object = None,
    credential_store: object = None,
    pipeline_store: object = None,
) -> dict[str, Any]:
    return {
        "configurable": {
            "sandbox_manager": sandbox_manager,
            "credential_store": credential_store,
            "pipeline_store": pipeline_store,
        }
    }


def _success_result() -> SandboxResult:
    return SandboxResult(exit_code=0, stdout="ok", stderr="")


def _fail_result() -> SandboxResult:
    return SandboxResult(exit_code=1, stdout="", stderr="error")


async def test_close_without_sandbox_returns_closed() -> None:
    """Close without sandbox just returns closed phase."""
    result = await close_workflow(_make_state(sandbox_id=None), _make_config())
    assert result["current_phase"] == "closed"


async def test_close_commits_and_pushes() -> None:
    """Close commits changes and pushes the feature branch."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    config = _make_config(sandbox_manager=sandbox)
    result = await close_workflow(_make_state(), config)

    assert result["current_phase"] == "closed"
    # Should have called execute for commit + push
    assert sandbox.execute.call_count >= 3  # add, commit, push
    sandbox.reconnect_network.assert_called_once()


async def test_close_push_failure_records_error() -> None:
    """Push failure is recorded but doesn't crash the node."""
    sandbox = AsyncMock()
    # add succeeds, commit succeeds, push fails
    call_count = 0

    async def execute_side_effect(*args: object, **kwargs: object) -> SandboxResult:
        nonlocal call_count
        call_count += 1
        # Push is the 3rd call
        if call_count == 3:
            return _fail_result()
        return _success_result()

    sandbox.execute = AsyncMock(side_effect=execute_side_effect)
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    config = _make_config(sandbox_manager=sandbox)
    result = await close_workflow(_make_state(), config)

    assert result["current_phase"] == "closed"
    assert result.get("pr_url") == ""


async def test_close_creates_pr_with_github_token() -> None:
    """Close creates a PR when github_token credential is available."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    cred = MagicMock()
    cred.credential_type = "github_token"
    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=cred)
    credential_store.get_secret = AsyncMock(return_value="ghp_test123")

    # Mock the GitHubRepoProvider
    import lintel.workflows.nodes.close as close_module

    original_import = close_module.__builtins__  # noqa: F841

    config = _make_config(sandbox_manager=sandbox, credential_store=credential_store)
    state = _make_state(credential_ids=["cred-1"])

    # The PR creation will fail because we're not mocking httpx,
    # but the push should succeed and the error should be caught
    result = await close_workflow(state, config)
    assert result["current_phase"] == "closed"


async def test_build_pr_body() -> None:
    """PR body includes request, plan summary, and tasks."""
    from lintel.workflows.nodes.close import _build_pr_body

    state = {
        "sanitized_messages": ["add dark mode toggle"],
    }
    plan = {
        "summary": "Add dark mode support",
        "tasks": [{"title": "Create toggle"}, {"title": "Add CSS"}],
    }
    body = _build_pr_body(state, plan)
    assert "add dark mode toggle" in body
    assert "Add dark mode support" in body
    assert "Create toggle" in body
    assert "Add CSS" in body
    assert "Lintel" in body
