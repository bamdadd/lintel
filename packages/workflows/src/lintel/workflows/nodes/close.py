"""Close node: commits, pushes, and creates a pull request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langchain_core.runnables import RunnableConfig

    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


async def close_workflow(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Push the feature branch and create a pull request."""
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    _config = config or {}
    tracker = StageTracker(_config, state)
    _configurable = _config.get("configurable", {})
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")

    # Fall back to runtime registry after LangGraph interrupt/resume
    run_id = state.get("run_id", "")
    if sandbox_manager is None and run_id:
        from lintel.workflows.nodes._runtime_registry import get_sandbox_manager

        sandbox_manager = get_sandbox_manager(run_id)

    # Release sandbox back to pool (clear pipeline_id allocation)
    async def _release_sandbox() -> None:
        sandbox_id = state.get("sandbox_id")
        if not sandbox_id:
            return
        sandbox_store = _configurable.get("sandbox_store")
        if sandbox_store is None:
            app_st = _configurable.get("app_state")
            if app_st is None and run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                app_st = get_app_state(run_id)
            if app_st is not None:
                sandbox_store = getattr(app_st, "sandbox_store", None)
        if sandbox_store is not None:
            try:
                entry = await sandbox_store.get(sandbox_id)
                if entry is not None:
                    entry.pop("pipeline_id", None)
                    await sandbox_store.update(sandbox_id, entry)
            except Exception:
                logger.warning("sandbox_release_failed", sandbox_id=sandbox_id[:12])

    # Check if pipeline is being aborted due to a failed stage
    has_failure = False
    for output in state.get("agent_outputs", []):
        if isinstance(output, dict) and output.get("verdict") in (
            "failed",
            "request_changes",
        ):
            has_failure = True
            break
    if state.get("error"):
        has_failure = True

    if has_failure:
        await tracker.append_log(
            "close", "Pipeline has failures — will raise draft PR for engineer handoff"
        )
        # Mark remaining pending/running stages as skipped
        await _skip_remaining_stages(_config, state)

    await tracker.mark_running("close")

    sandbox_id = state.get("sandbox_id")
    feature_branch = state.get("feature_branch", "")
    base_branch = state.get("repo_branch", "main")
    repo_url = state.get("repo_url", "")
    workdir = state.get("workspace_path", "/workspace/repo")
    workspace_paths: tuple[tuple[str, str], ...] = state.get("workspace_paths", ())

    if not sandbox_id or sandbox_manager is None:
        await tracker.mark_completed("close")
        await _release_sandbox()
        return {"current_phase": "closed"}

    # Build the list of (repo_url, workdir) pairs to commit/push
    # Primary repo is always first; additional repos follow
    repos_to_close: list[tuple[str, str]] = []
    if workspace_paths:
        repos_to_close = list(workspace_paths)
    elif repo_url:
        repos_to_close = [(repo_url, workdir)]

    # Commit any uncommitted changes across all repos
    await tracker.append_log("close", "Committing changes...")
    messages = state.get("sanitized_messages", [])
    commit_msg = messages[0][:72] if messages else "lintel: implement feature"
    # Escape double quotes in commit message for shell safety
    safe_msg = commit_msg.replace('"', '\\"')

    for _r_url, wd in repos_to_close:
        commit_cmds = [
            f"cd {wd} && git config user.email 'lintel@lintel.dev'",
            f"cd {wd} && git config user.name 'Lintel'",
            f"cd {wd} && git add -A",
            f'cd {wd} && git diff --cached --quiet || git commit -m "{safe_msg}"',
        ]
        for cmd in commit_cmds:
            result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command=cmd, timeout_seconds=30),
            )
            if result.exit_code != 0 and "git diff" not in cmd:
                logger.warning("close_commit_step_failed", cmd=cmd[:80], error=result.stderr[:200])

    pr_url = ""
    push_error = ""
    all_pr_urls: list[str] = []

    if feature_branch and repos_to_close:
        # Reconnect network for push
        try:
            await sandbox_manager.reconnect_network(sandbox_id)
        except Exception:
            logger.warning("close_reconnect_network_failed")

        # Resolve credentials for push — reuse setup_workspace's resolver
        from lintel.workflows.nodes.setup_workspace import resolve_credentials

        credential_store = _configurable.get("credential_store")
        if credential_store is None and run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            _app_state = get_app_state(run_id)
            if _app_state is not None:
                credential_store = getattr(_app_state, "credential_store", None)

        # Push each repo
        for r_url, wd in repos_to_close:
            if not r_url:
                continue

            # Inject credentials into remote URL
            if credential_store is not None:
                auth_url, _ = await resolve_credentials(
                    state, credential_store, sandbox_manager, sandbox_id, r_url
                )
                if auth_url != r_url:
                    set_url_cmd = f"cd {wd} && git remote set-url origin {auth_url}"
                    await sandbox_manager.execute(
                        sandbox_id,
                        SandboxJob(command=set_url_cmd, timeout_seconds=10),
                    )

            # Fetch latest remote refs before pushing
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=f"cd {wd} && git fetch origin 2>&1 || true",
                    timeout_seconds=30,
                ),
            )

            repo_label = r_url.rstrip("/").rsplit("/", 1)[-1]
            await tracker.append_log("close", f"Pushing branch {feature_branch} to {repo_label}...")

            # Retry push up to 3 times — force-with-lease can fail on stale refs
            push_result = None
            for push_attempt in range(3):
                if push_attempt > 0:
                    await tracker.append_log(
                        "close", f"Retrying push (attempt {push_attempt + 1}/3)..."
                    )
                    await sandbox_manager.execute(
                        sandbox_id,
                        SandboxJob(
                            command=f"cd {wd} && git fetch origin 2>&1 || true",
                            timeout_seconds=30,
                        ),
                    )
                push_result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(
                        command=(
                            f"cd {wd} && git push --force-with-lease -u origin {feature_branch}"
                        ),
                        timeout_seconds=60,
                    ),
                )
                if push_result.exit_code == 0:
                    break
                push_output = push_result.stderr or push_result.stdout
                # Only retry on stale ref errors; other failures are not transient
                if "stale info" not in (push_output or ""):
                    break

            if push_result and push_result.exit_code != 0:
                repo_push_error = push_result.stderr or push_result.stdout
                # Last resort: force push if force-with-lease keeps failing
                await tracker.append_log(
                    "close", "force-with-lease failed, falling back to force push..."
                )
                push_result = await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(
                        command=(f"cd {wd} && git push --force -u origin {feature_branch}"),
                        timeout_seconds=60,
                    ),
                )
            if push_result and push_result.exit_code != 0:
                repo_push_error = push_result.stderr or push_result.stdout
                logger.warning("close_push_failed", repo=repo_label, error=repo_push_error[:200])
                await tracker.append_log(
                    "close", f"Push failed ({repo_label}): {repo_push_error[:200]}"
                )
                if not push_error:
                    push_error = repo_push_error
            else:
                await tracker.append_log("close", f"Push succeeded ({repo_label})")

                # Create PR
                this_pr = await _create_pull_request(
                    _config,
                    state,
                    repo_url=r_url,
                    feature_branch=feature_branch,
                    base_branch=base_branch,
                    commit_msg=commit_msg,
                    draft=has_failure,
                )
                if this_pr:
                    all_pr_urls.append(this_pr)

        pr_url = all_pr_urls[0] if all_pr_urls else ""

        # Disconnect network again
        import contextlib

        with contextlib.suppress(Exception):
            await sandbox_manager.disconnect_network(sandbox_id)

    # Update work item with PR URL(s)
    if pr_url:
        work_item_store = _configurable.get(
            "work_item_store",
            getattr(_configurable.get("app_state"), "work_item_store", None),
        )
        work_item_id = state.get("work_item_id", "")
        if work_item_store and work_item_id:
            try:
                item = await work_item_store.get(work_item_id)
                if item is not None:
                    item["pr_url"] = pr_url
                    if len(all_pr_urls) > 1:
                        item["pr_urls"] = all_pr_urls
                    await work_item_store.update(work_item_id, item)
            except Exception:
                logger.warning("close_update_work_item_failed")

    stage_outputs: dict[str, object] = {}
    if pr_url:
        stage_outputs["pr_url"] = pr_url
    if all_pr_urls and len(all_pr_urls) > 1:
        stage_outputs["pr_urls"] = all_pr_urls
    if push_error:
        stage_outputs["push_error"] = push_error

    if pr_url:
        await tracker.mark_completed("close", outputs=stage_outputs)
    else:
        await tracker.mark_completed(
            "close",
            outputs=stage_outputs or None,
            error=push_error or "No PR raised",
        )

    await _release_sandbox()
    return {
        "current_phase": "closed",
        "pr_url": pr_url,
    }


async def _create_pull_request(
    config: Mapping[str, Any],
    state: ThreadWorkflowState,
    *,
    repo_url: str,
    feature_branch: str,
    base_branch: str,
    commit_msg: str,
    draft: bool = False,
) -> str:
    """Create a PR using an injected repo_provider or credentials.

    When *draft* is True the PR is opened as a draft with a warning banner
    so an engineer knows it needs manual attention.

    Returns the PR URL, or empty string if creation is skipped/fails.
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)
    _configurable = config.get("configurable", {})
    pr_url = ""

    plan = state.get("plan", {})
    pr_body = _build_pr_body(state, plan, draft=draft)
    pr_title = f"[WIP] {commit_msg}" if draft else commit_msg
    label = "draft pull request" if draft else "pull request"

    # Prefer injected repo_provider (used by tests)
    repo_provider = _configurable.get("repo_provider")
    if repo_provider is not None:
        try:
            await tracker.append_log("close", f"Creating {label}...")
            pr_url = await repo_provider.create_pr(
                repo_url=repo_url,
                head=feature_branch,
                base=base_branch,
                title=pr_title,
                body=pr_body,
                draft=draft,
            )
            await tracker.append_log("close", f"PR created: {pr_url}")

            # Add review comment if available
            review_outputs = [
                o
                for o in state.get("agent_outputs", [])
                if isinstance(o, dict) and o.get("node") == "review"
            ]
            if review_outputs:
                review_text = review_outputs[0].get("output", "")
                if review_text:
                    pr_number = int(pr_url.rstrip("/").split("/")[-1])
                    await repo_provider.add_comment(repo_url, pr_number, review_text)
        except Exception as exc:
            logger.warning("close_pr_creation_failed", error=str(exc)[:200])
        return pr_url

    # Fall back to credential-based GitHubRepoProvider
    credential_store = _configurable.get("credential_store")
    run_id = state.get("run_id", "")
    if credential_store is None and run_id:
        from lintel.workflows.nodes._runtime_registry import get_app_state

        _app_state = get_app_state(run_id)
        if _app_state is not None:
            credential_store = getattr(_app_state, "credential_store", None)

    if credential_store is None:
        return ""

    from lintel.workflows.nodes.setup_workspace import resolve_github_token

    github_token = await resolve_github_token(state, credential_store)
    if not github_token:
        return ""

    from lintel.repos.github_provider import GitHubRepoProvider

    provider = GitHubRepoProvider(token=github_token)
    try:
        await tracker.append_log("close", f"Creating {label}...")
        pr_url = await provider.create_pr(
            repo_url=repo_url,
            head=feature_branch,
            base=base_branch,
            title=pr_title,
            body=pr_body,
            draft=draft,
        )
        await tracker.append_log("close", f"PR created: {pr_url}")

        # Add review comment if available
        review_outputs = [
            o
            for o in state.get("agent_outputs", [])
            if isinstance(o, dict) and o.get("node") == "review"
        ]
        if review_outputs:
            review_text = review_outputs[0].get("output", "")
            if review_text:
                pr_number = int(pr_url.rstrip("/").split("/")[-1])
                await provider.add_comment(repo_url, pr_number, review_text)
    except Exception as exc:
        logger.warning("close_pr_creation_failed", error=str(exc)[:200])

    return pr_url


async def _skip_remaining_stages(
    config: Mapping[str, Any],
    state: ThreadWorkflowState,
) -> None:
    """Mark all pending/running stages as skipped when pipeline aborts."""
    from dataclasses import replace

    from lintel.workflows.types import StageStatus

    run_id = state.get("run_id", "")
    if not run_id:
        return

    # Get pipeline store via registry fallback
    configurable = config.get("configurable", {})
    pipeline_store = configurable.get("pipeline_store")
    if pipeline_store is None:
        app_state = configurable.get("app_state")
        if app_state is None and run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            app_state = get_app_state(run_id)
        if app_state is not None:
            pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return

    try:
        run = await pipeline_store.get(run_id)
        if run is None:
            return
        updated_stages = []
        for s in run.stages:
            if isinstance(s, dict):
                from lintel.workflows.types import Stage

                s = Stage(**s)
            if s.status in (StageStatus.PENDING, StageStatus.RUNNING):
                updated_stages.append(replace(s, status=StageStatus.SKIPPED))
            else:
                updated_stages.append(s)
        updated = replace(run, stages=tuple(updated_stages), status="failed")
        await pipeline_store.update(updated)
    except Exception:
        logger.warning("skip_remaining_stages_failed", run_id=run_id)


def _build_pr_body(
    state: ThreadWorkflowState,
    plan: dict[str, Any],
    *,
    draft: bool = False,
) -> str:
    """Build a well-structured PR description from the workflow state."""
    lines: list[str] = []

    if draft:
        lines.append(
            "> :warning: **This is a draft PR created by Lintel after a pipeline failure.**\n"
            "> The automated workflow could not complete successfully. "
            "An engineer should review the changes, fix any issues, and mark the PR as ready.\n"
        )

    # Summary section
    messages = state.get("sanitized_messages", [])
    summary = plan.get("summary", "")
    if summary:
        lines.append(f"## Summary\n\n{summary}\n")
    elif messages:
        lines.append(f"## Summary\n\n{messages[0]}\n")

    # What changed
    tasks = plan.get("tasks", [])
    if tasks:
        lines.append("## Changes\n")
        for task in tasks:
            title = task.get("title", task) if isinstance(task, dict) else str(task)
            lines.append(f"- [x] {title}")
        lines.append("")

    # Context — original request if we have a summary too
    if summary and messages:
        lines.append(f"## Context\n\n> {messages[0]}\n")

    # Review findings
    review_outputs = [
        o
        for o in state.get("agent_outputs", [])
        if isinstance(o, dict) and o.get("node") == "review"
    ]
    if review_outputs:
        verdict = review_outputs[0].get("verdict", "")
        if verdict == "approve":
            lines.append("## Review\n\n:white_check_mark: Automated review passed.\n")

    # Test results
    test_outputs = [
        o for o in state.get("agent_outputs", []) if isinstance(o, dict) and o.get("node") == "test"
    ]
    if test_outputs:
        test_verdict = test_outputs[0].get("verdict", "")
        if test_verdict == "passed":
            lines.append("## Tests\n\n:white_check_mark: All tests passing.\n")

    lines.append("---\n*Raised by [Lintel](https://github.com/bamdadd/lintel)* :robot:")
    return "\n".join(lines)
