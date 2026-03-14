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
    from unittest.mock import patch

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    cred = MagicMock()
    cred.credential_type = "github_token"
    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=cred)
    credential_store.get_secret = AsyncMock(return_value="ghp_test123")

    mock_provider = AsyncMock()
    mock_provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/42")
    mock_provider.add_comment = AsyncMock()

    config = _make_config(sandbox_manager=sandbox, credential_store=credential_store)
    state = _make_state(credential_ids=["cred-1"])

    with patch(
        "lintel.repos.github_provider.GitHubRepoProvider",
        return_value=mock_provider,
    ):
        result = await close_workflow(state, config)

    assert result["current_phase"] == "closed"
    assert result["pr_url"] == "https://github.com/test/repo/pull/42"
    mock_provider.create_pr.assert_called_once_with(
        repo_url="https://github.com/test/repo",
        head="lintel/feat/dark-mode",
        base="main",
        title="add dark mode toggle",
        body=mock_provider.create_pr.call_args.kwargs["body"],
    )
    # Verify the PR body contains key information
    pr_body = mock_provider.create_pr.call_args.kwargs["body"]
    assert "Add dark mode" in pr_body
    assert "Toggle component" in pr_body
    assert "Lintel" in pr_body


async def test_close_creates_pr_with_review_comment() -> None:
    """Close adds review output as a PR comment."""
    from unittest.mock import patch

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    cred = MagicMock()
    cred.credential_type = "github_token"
    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=cred)
    credential_store.get_secret = AsyncMock(return_value="ghp_test123")

    mock_provider = AsyncMock()
    mock_provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/7")
    mock_provider.add_comment = AsyncMock()

    config = _make_config(sandbox_manager=sandbox, credential_store=credential_store)
    state = _make_state(
        credential_ids=["cred-1"],
        agent_outputs=[{"node": "review", "verdict": "approve", "output": "LGTM, ship it!"}],
    )

    with patch(
        "lintel.repos.github_provider.GitHubRepoProvider",
        return_value=mock_provider,
    ):
        result = await close_workflow(state, config)

    assert result["pr_url"] == "https://github.com/test/repo/pull/7"
    mock_provider.add_comment.assert_called_once_with(
        "https://github.com/test/repo", 7, "LGTM, ship it!"
    )


async def test_close_injects_token_into_remote_url() -> None:
    """Close injects the github token into the git remote URL for pushing."""
    from unittest.mock import patch

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    cred = MagicMock()
    cred.credential_type = "github_token"
    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=cred)
    credential_store.get_secret = AsyncMock(return_value="ghp_secret_token")

    mock_provider = AsyncMock()
    mock_provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/1")
    mock_provider.add_comment = AsyncMock()

    config = _make_config(sandbox_manager=sandbox, credential_store=credential_store)
    state = _make_state(credential_ids=["cred-1"])

    with patch(
        "lintel.repos.github_provider.GitHubRepoProvider",
        return_value=mock_provider,
    ):
        await close_workflow(state, config)

    # Find the set-url call — should contain the token
    set_url_calls = [call for call in sandbox.execute.call_args_list if "set-url" in str(call)]
    assert len(set_url_calls) == 1
    cmd = str(set_url_calls[0])
    assert "x-access-token:ghp_secret_token@" in cmd


async def test_build_pr_body_with_plan() -> None:
    """PR body includes summary, tasks, and context."""
    from lintel.workflows.nodes.close import _build_pr_body

    state: dict[str, Any] = {
        "sanitized_messages": ["add dark mode toggle"],
        "agent_outputs": [],
    }
    plan: dict[str, Any] = {
        "summary": "Add dark mode support",
        "tasks": [{"title": "Create toggle"}, {"title": "Add CSS"}],
    }
    body = _build_pr_body(state, plan)
    assert "Add dark mode support" in body
    assert "Create toggle" in body
    assert "Add CSS" in body
    assert "add dark mode toggle" in body  # Context section
    assert "Raised by" in body
    assert "Lintel" in body


async def test_build_pr_body_without_plan() -> None:
    """PR body falls back to request message when no plan summary."""
    from lintel.workflows.nodes.close import _build_pr_body

    state: dict[str, Any] = {
        "sanitized_messages": ["fix the login bug"],
        "agent_outputs": [],
    }
    body = _build_pr_body(state, {})
    assert "fix the login bug" in body
    assert "Raised by" in body


async def test_build_pr_body_includes_review_and_test_status() -> None:
    """PR body shows review and test pass status."""
    from lintel.workflows.nodes.close import _build_pr_body

    state: dict[str, Any] = {
        "sanitized_messages": ["add feature"],
        "agent_outputs": [
            {"node": "test", "verdict": "passed", "output": "all green"},
            {"node": "review", "verdict": "approve", "output": "looks good"},
        ],
    }
    plan: dict[str, Any] = {"summary": "New feature", "tasks": []}
    body = _build_pr_body(state, plan)
    assert "review passed" in body.lower() or "Review" in body
    assert "tests passing" in body.lower() or "Tests" in body
