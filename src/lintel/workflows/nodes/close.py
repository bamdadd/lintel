"""Close node: commits, pushes, and creates a pull request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.contracts.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


async def close_workflow(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Push the feature branch and create a pull request."""
    from lintel.contracts.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import (
        append_log,
        mark_completed,
        mark_running,
    )

    _config = config or {}
    _configurable = _config.get("configurable", {})
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")

    await mark_running(_config, "merge", state)

    sandbox_id = state.get("sandbox_id")
    feature_branch = state.get("feature_branch", "")
    base_branch = state.get("repo_branch", "main")
    repo_url = state.get("repo_url", "")
    workdir = state.get("workspace_path", "/workspace/repo")

    if not sandbox_id or sandbox_manager is None:
        await mark_completed(_config, "merge", state)
        return {"current_phase": "closed"}

    # Commit any uncommitted changes
    await append_log(_config, "merge", "Committing changes...", state)
    messages = state.get("sanitized_messages", [])
    commit_msg = messages[0][:72] if messages else "lintel: implement feature"

    commit_cmds = [
        f"cd {workdir} && git add -A",
        f'cd {workdir} && git diff --cached --quiet || git commit -m "{commit_msg}"',
    ]
    for cmd in commit_cmds:
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=cmd, timeout_seconds=30),
        )

    pr_url = ""
    push_error = ""

    if feature_branch and repo_url:
        # Reconnect network for push
        try:
            await sandbox_manager.reconnect_network(sandbox_id)
        except Exception:
            logger.warning("close_reconnect_network_failed")

        # Resolve credentials for push
        credential_store = _configurable.get("credential_store")
        if credential_store is not None:
            credential_ids = state.get("credential_ids", [])
            for cred_id in credential_ids:
                try:
                    cred = await credential_store.get(cred_id)
                    if cred is None:
                        continue
                    secret = await credential_store.get_secret(cred_id)
                    if not secret:
                        continue
                    cred_type = cred.credential_type
                    if hasattr(cred_type, "value"):
                        cred_type = cred_type.value
                    if cred_type == "github_token":
                        # Inject token into remote URL
                        import re

                        auth_url = re.sub(
                            r"https://",
                            f"https://x-access-token:{secret}@",
                            repo_url,
                        )
                        set_url_cmd = f"cd {workdir} && git remote set-url origin {auth_url}"
                        await sandbox_manager.execute(
                            sandbox_id,
                            SandboxJob(command=set_url_cmd, timeout_seconds=10),
                        )
                        break
                except Exception:
                    logger.warning("close_credential_resolve_failed", cred_id=cred_id)

        # Push
        await append_log(_config, "merge", f"Pushing branch {feature_branch}...", state)
        push_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"cd {workdir} && git push -u origin {feature_branch}",
                timeout_seconds=60,
            ),
        )
        if push_result.exit_code != 0:
            push_error = push_result.stderr or push_result.stdout
            logger.warning("close_push_failed", error=push_error[:200])
            await append_log(_config, "merge", f"Push failed: {push_error[:200]}", state)
        else:
            await append_log(_config, "merge", "Push succeeded", state)

            # Create PR via GitHub API
            if credential_store is not None:
                credential_ids = state.get("credential_ids", [])
                for cred_id in credential_ids:
                    try:
                        cred = await credential_store.get(cred_id)
                        if cred is None:
                            continue
                        secret = await credential_store.get_secret(cred_id)
                        cred_type = cred.credential_type
                        if hasattr(cred_type, "value"):
                            cred_type = cred_type.value
                        if cred_type == "github_token" and secret:
                            from lintel.infrastructure.repos.github_provider import (
                                GitHubRepoProvider,
                            )

                            provider = GitHubRepoProvider(token=secret)
                            plan = state.get("plan", {})
                            pr_title = commit_msg
                            pr_body = _build_pr_body(state, plan)

                            await append_log(_config, "merge", "Creating pull request...", state)
                            pr_url = await provider.create_pr(
                                repo_url=repo_url,
                                head=feature_branch,
                                base=base_branch,
                                title=pr_title,
                                body=pr_body,
                            )
                            await append_log(_config, "merge", f"PR created: {pr_url}", state)

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
                            break
                    except Exception as exc:
                        logger.warning(
                            "close_pr_creation_failed",
                            error=str(exc)[:200],
                        )

        # Disconnect network again
        import contextlib

        with contextlib.suppress(Exception):
            await sandbox_manager.disconnect_network(sandbox_id)

    # Update work item with PR URL
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
                    await work_item_store.update(work_item_id, item)
            except Exception:
                logger.warning("close_update_work_item_failed")

    stage_outputs: dict[str, object] = {}
    if pr_url:
        stage_outputs["pr_url"] = pr_url
    if push_error:
        stage_outputs["push_error"] = push_error
    await mark_completed(_config, "merge", state, outputs=stage_outputs or None)

    return {
        "current_phase": "closed",
        "pr_url": pr_url,
    }


def _build_pr_body(state: dict[str, Any], plan: dict[str, Any]) -> str:
    """Build a PR description from the workflow state."""
    lines = ["## Summary\n"]

    messages = state.get("sanitized_messages", [])
    if messages:
        lines.append(f"**Request:** {messages[0]}\n")

    summary = plan.get("summary", "")
    if summary:
        lines.append(f"**Plan:** {summary}\n")

    tasks = plan.get("tasks", [])
    if tasks:
        lines.append("## Tasks\n")
        for task in tasks:
            title = task.get("title", task) if isinstance(task, dict) else str(task)
            lines.append(f"- [x] {title}")
        lines.append("")

    lines.append("---\n*Created by [Lintel](https://github.com/bamdadd/lintel)*")
    return "\n".join(lines)
