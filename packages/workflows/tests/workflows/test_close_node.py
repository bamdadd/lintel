"""Tests for the close workflow node (PR creation and push)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from lintel.repos.types import PrAlreadyExistsError, PrAuthError, PrTransientError
from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes.close import (
    _create_pr_with_retry,
    close_workflow,
)


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
        draft=False,
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


async def test_close_emits_audit_entry() -> None:
    """Close node emits an audit entry when audit_entry_store is available."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    audit_entries: list[Any] = []
    audit_store = AsyncMock()
    audit_store.add = AsyncMock(side_effect=lambda e: audit_entries.append(e))

    app_state = MagicMock()
    app_state.audit_entry_store = audit_store
    app_state.sandbox_store = None

    pipeline_store = AsyncMock()
    pipeline_store.get = AsyncMock(return_value=None)

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "pipeline_store": pipeline_store,
            "app_state": app_state,
        }
    }

    await close_workflow(_make_state(), config)

    assert len(audit_entries) == 1
    entry = audit_entries[0]
    assert entry.action in ("pr_created", "pipeline_closed")
    assert entry.resource_type == "pipeline_run"
    assert entry.resource_id == "run-1"


# --- PR creation retry tests ---


async def test_create_pr_with_retry_succeeds_first_attempt() -> None:
    """PR creation succeeds on the first attempt — no retries."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/1")
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == "https://github.com/test/repo/pull/1"
    assert provider.create_pr.call_count == 1


@patch("lintel.workflows.nodes.close.asyncio.sleep", new_callable=AsyncMock)
async def test_create_pr_with_retry_succeeds_on_second_attempt(
    mock_sleep: AsyncMock,
) -> None:
    """PR creation fails once then succeeds — verifies retry + backoff."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(
        side_effect=[
            PrTransientError("rate limit exceeded", status_code=429),
            "https://github.com/test/repo/pull/2",
        ]
    )
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == "https://github.com/test/repo/pull/2"
    assert provider.create_pr.call_count == 2
    mock_sleep.assert_called_once_with(1.0)  # 2^0 = 1


@patch("lintel.workflows.nodes.close.asyncio.sleep", new_callable=AsyncMock)
async def test_create_pr_with_retry_succeeds_on_third_attempt(
    mock_sleep: AsyncMock,
) -> None:
    """PR creation fails twice then succeeds on the third attempt."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(
        side_effect=[
            PrTransientError("server error", status_code=500),
            PrTransientError("rate limit exceeded", status_code=429),
            "https://github.com/test/repo/pull/3",
        ]
    )
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == "https://github.com/test/repo/pull/3"
    assert provider.create_pr.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1.0)  # 2^0
    mock_sleep.assert_any_call(2.0)  # 2^1


@patch("lintel.workflows.nodes.close.asyncio.sleep", new_callable=AsyncMock)
async def test_create_pr_with_retry_exhausts_all_attempts(
    mock_sleep: AsyncMock,
) -> None:
    """PR creation fails all 3 attempts — returns empty string."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(side_effect=PrTransientError("API down", status_code=503))
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == ""
    assert provider.create_pr.call_count == 3
    assert mock_sleep.call_count == 2


@patch("lintel.workflows.nodes.close.asyncio.sleep", new_callable=AsyncMock)
async def test_close_retries_pr_creation_via_repo_provider(
    mock_sleep: AsyncMock,
) -> None:
    """Full close_workflow retries PR creation when using injected repo_provider."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    repo_provider = AsyncMock()
    repo_provider.create_pr = AsyncMock(
        side_effect=[
            PrTransientError("GitHub API timeout", status_code=504),
            "https://github.com/test/repo/pull/99",
        ]
    )
    repo_provider.add_comment = AsyncMock()

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "repo_provider": repo_provider,
        }
    }
    result = await close_workflow(_make_state(), config)

    assert result["pr_url"] == "https://github.com/test/repo/pull/99"
    assert repo_provider.create_pr.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("lintel.workflows.nodes.close.asyncio.sleep", new_callable=AsyncMock)
async def test_close_retries_pr_creation_via_credentials(
    mock_sleep: AsyncMock,
) -> None:
    """Full close_workflow retries PR creation when using credential-based provider."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    cred = MagicMock()
    cred.credential_type = "github_token"
    credential_store = AsyncMock()
    credential_store.get = AsyncMock(return_value=cred)
    credential_store.get_secret = AsyncMock(return_value="ghp_test")

    mock_provider = AsyncMock()
    mock_provider.create_pr = AsyncMock(
        side_effect=[
            PrTransientError("rate limit", status_code=429),
            "https://github.com/test/repo/pull/50",
        ]
    )
    mock_provider.add_comment = AsyncMock()

    config = _make_config(sandbox_manager=sandbox, credential_store=credential_store)
    state = _make_state(credential_ids=["cred-1"])

    with patch(
        "lintel.repos.github_provider.GitHubRepoProvider",
        return_value=mock_provider,
    ):
        result = await close_workflow(state, config)

    assert result["pr_url"] == "https://github.com/test/repo/pull/50"
    assert mock_provider.create_pr.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


# --- Already-exists error tests ---


async def test_create_pr_already_exists_finds_existing() -> None:
    """On PrAlreadyExistsError, find and return the existing PR URL."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(
        side_effect=PrAlreadyExistsError(
            "PR already exists", status_code=422, response_body="already exists"
        )
    )
    provider.find_existing_pr = AsyncMock(return_value="https://github.com/test/repo/pull/10")
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == "https://github.com/test/repo/pull/10"
    assert provider.create_pr.call_count == 1
    provider.find_existing_pr.assert_called_once_with(
        "https://github.com/test/repo", "feat/x", "main"
    )


async def test_create_pr_already_exists_fallback_list() -> None:
    """On PrAlreadyExistsError without find_existing_pr, falls back to list_pull_requests."""
    provider = AsyncMock(spec=["create_pr", "list_pull_requests"])
    provider.create_pr = AsyncMock(
        side_effect=PrAlreadyExistsError(
            "PR already exists", status_code=422, response_body="already exists"
        )
    )
    provider.list_pull_requests = AsyncMock(
        return_value=[
            {
                "head_branch": "feat/x",
                "base_branch": "main",
                "html_url": "https://github.com/test/repo/pull/11",
            },
        ]
    )
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == "https://github.com/test/repo/pull/11"


async def test_create_pr_already_exists_not_found() -> None:
    """On PrAlreadyExistsError when existing PR cannot be located, returns empty."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(
        side_effect=PrAlreadyExistsError(
            "PR already exists", status_code=422, response_body="already exists"
        )
    )
    provider.find_existing_pr = AsyncMock(return_value="")
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == ""


# --- Auth error tests ---


async def test_create_pr_auth_error_no_retry() -> None:
    """Auth errors (401/403) are not retried and surface a clear message."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(
        side_effect=PrAuthError("Bad credentials", status_code=401, response_body="Bad credentials")
    )
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == ""
    assert provider.create_pr.call_count == 1  # No retry
    # Verify tracker logged the auth failure
    log_calls = [str(c) for c in tracker.append_log.call_args_list]
    assert any("auth failure" in c for c in log_calls)


# --- Non-classified error tests ---


async def test_create_pr_unknown_error_no_retry() -> None:
    """Non-classified errors (e.g. plain RuntimeError) are not retried."""
    provider = AsyncMock()
    provider.create_pr = AsyncMock(side_effect=RuntimeError("unexpected"))
    tracker = AsyncMock()

    result = await _create_pr_with_retry(
        provider,
        tracker,
        "pull request",
        "https://github.com/test/repo",
        "feat/x",
        "main",
        "add feature",
        "body",
        False,
    )

    assert result == ""
    assert provider.create_pr.call_count == 1


# --- Work item update tests ---


def _make_work_item_config(
    sandbox_manager: object = None,
    repo_provider: object = None,
    work_item_store: object = None,
) -> dict[str, Any]:
    """Build config dict with work_item_store for testing work item updates."""
    return {
        "configurable": {
            "sandbox_manager": sandbox_manager,
            "repo_provider": repo_provider,
            "work_item_store": work_item_store,
        }
    }


async def test_close_updates_work_item_with_pr_url_and_in_review() -> None:
    """Successful PR creation updates work item to in_review with pr_url."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    repo_provider = AsyncMock()
    repo_provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/42")
    repo_provider.add_comment = AsyncMock()

    work_item_store = AsyncMock()
    stored_item: dict[str, Any] = {
        "work_item_id": "wi-1",
        "status": "in_progress",
        "pr_url": "",
        "description": "Build login page",
    }
    work_item_store.get = AsyncMock(return_value=stored_item)
    work_item_store.update = AsyncMock()

    config = _make_work_item_config(
        sandbox_manager=sandbox,
        repo_provider=repo_provider,
        work_item_store=work_item_store,
    )
    state = _make_state(work_item_id="wi-1")

    result = await close_workflow(state, config)

    assert result["pr_url"] == "https://github.com/test/repo/pull/42"
    work_item_store.update.assert_called_once()
    update_call = work_item_store.update.call_args
    assert update_call[0][0] == "wi-1"
    updated_data = update_call[0][1]
    assert updated_data["status"] == "in_review"
    assert updated_data["pr_url"] == "https://github.com/test/repo/pull/42"


async def test_close_work_item_update_failure_does_not_crash() -> None:
    """If work item store update fails after PR creation, node still succeeds."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_success_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    repo_provider = AsyncMock()
    repo_provider.create_pr = AsyncMock(return_value="https://github.com/test/repo/pull/99")
    repo_provider.add_comment = AsyncMock()

    work_item_store = AsyncMock()
    work_item_store.get = AsyncMock(side_effect=RuntimeError("store down"))

    config = _make_work_item_config(
        sandbox_manager=sandbox,
        repo_provider=repo_provider,
        work_item_store=work_item_store,
    )
    state = _make_state(work_item_id="wi-1")

    # Should not raise
    result = await close_workflow(state, config)
    assert result["pr_url"] == "https://github.com/test/repo/pull/99"
    assert result["current_phase"] == "closed"


async def test_close_reverts_work_item_to_open_on_pr_failure() -> None:
    """Failed PR creation reverts work item status to open with failure note."""
    sandbox = AsyncMock()
    # Push will fail
    sandbox.execute = AsyncMock(return_value=_fail_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    work_item_store = AsyncMock()
    stored_item: dict[str, Any] = {
        "work_item_id": "wi-fail",
        "status": "in_progress",
        "pr_url": "",
        "description": "Build login page",
    }
    work_item_store.get = AsyncMock(return_value=stored_item)
    work_item_store.update = AsyncMock()

    config = _make_work_item_config(
        sandbox_manager=sandbox,
        work_item_store=work_item_store,
    )
    state = _make_state(work_item_id="wi-fail")

    result = await close_workflow(state, config)

    assert result.get("pr_url") == ""
    work_item_store.update.assert_called_once()
    update_call = work_item_store.update.call_args
    updated_data = update_call[0][1]
    assert updated_data["status"] == "open"
    assert "Pipeline failure" in updated_data["description"]


async def test_close_revert_failure_does_not_crash() -> None:
    """If reverting work item status fails, the node still completes."""
    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=_fail_result())
    sandbox.reconnect_network = AsyncMock()
    sandbox.disconnect_network = AsyncMock()

    work_item_store = AsyncMock()
    work_item_store.get = AsyncMock(side_effect=RuntimeError("store down"))

    config = _make_work_item_config(
        sandbox_manager=sandbox,
        work_item_store=work_item_store,
    )
    state = _make_state(work_item_id="wi-revert-fail")

    # Should not raise
    result = await close_workflow(state, config)
    assert result["current_phase"] == "closed"
