"""Setup workspace node — clones repo into sandbox and creates feature branch."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.api.routes.variables import InMemoryVariableStore
    from lintel.contracts.protocols import CredentialStore, RepoProvider, SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = logging.getLogger(__name__)


def _inject_github_token(repo_url: str, token: str) -> str:
    """Inject a GitHub token into a clone URL for authentication."""
    return re.sub(
        r"https://github\.com/",
        f"https://x-access-token:{token}@github.com/",
        repo_url,
    )


async def _resolve_credentials(
    state: ThreadWorkflowState,
    credential_store: CredentialStore | None,
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    repo_url: str,
) -> tuple[str, bool]:
    """Resolve credentials. Returns (clone_url, has_ssh_key)."""
    if credential_store is None:
        return repo_url, False

    credential_ids: tuple[str, ...] = state.get("credential_ids", ())
    if not credential_ids:
        return repo_url, False

    has_ssh_key = False
    for cred_id in credential_ids:
        cred = await credential_store.get(cred_id)
        if cred is None:
            continue

        secret = await credential_store.get_secret(cred_id)
        if not secret:
            continue

        if cred.credential_type == "github_token":
            repo_url = _inject_github_token(repo_url, secret)
        elif cred.credential_type == "ssh_key":
            from lintel.contracts.types import SandboxJob

            has_ssh_key = True
            await sandbox_manager.write_file(
                sandbox_id, "/tmp/ssh_key", secret
            )
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="chmod 600 /tmp/ssh_key", timeout_seconds=10),
            )

    return repo_url, has_ssh_key


async def setup_workspace(
    state: ThreadWorkflowState,
    config: RunnableConfig | None = None,
    *,
    sandbox_manager: SandboxManager,
    repo_provider: RepoProvider,
    credential_store: CredentialStore | None = None,
    variable_store: InMemoryVariableStore | None = None,
) -> dict[str, Any]:
    """Clone the project repo into a sandbox and create a feature branch.

    Expects project_id, repo_url, repo_branch, work_item_id, and feature_branch
    to be set in state (populated by the chat route before workflow dispatch).
    """
    from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef
    from lintel.workflows.nodes._stage_tracking import mark_completed, mark_running

    _config = config or {}
    await mark_running(_config, "setup_workspace", state)

    repo_url = state.get("repo_url", "")
    repo_urls: tuple[str, ...] = state.get("repo_urls", ())
    repo_branch = state.get("repo_branch", "main")
    feature_branch = state.get("feature_branch", "")
    work_item_id = state.get("work_item_id", "")

    if not repo_url:
        await mark_completed(_config, "setup_workspace", state, error="No repository URL")
        return {
            "error": "No repository URL configured for this project",
            "current_phase": "closed",
        }

    if not feature_branch:
        from lintel.workflows.nodes._branch_naming import generate_branch_name

        intent = state.get("intent", "feature")
        description = ""
        messages = state.get("sanitized_messages", [])
        if messages:
            description = messages[0][:60] if isinstance(messages[0], str) else ""
        feature_branch = (
            generate_branch_name(work_item_id, work_type=intent, description=description)
            if work_item_id
            else "lintel/task/work"
        )

    # Parse thread ref
    thread_ref_str = state["thread_ref"]
    parts = thread_ref_str.replace("thread:", "").split(":")
    thread_ref = ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )

    # Resolve environment variables if environment_id is set
    env_vars: frozenset[tuple[str, str]] = frozenset()
    environment_id = state.get("environment_id", "")
    if environment_id and variable_store is not None:
        variables = await variable_store.list_all(environment_id=environment_id)
        for var in variables:
            if var.is_secret:
                logger.warning(
                    "injecting_secret_variable_into_sandbox"
                    " key=%s environment_id=%s",
                    var.key,
                    environment_id,
                )
        env_vars = frozenset((var.key, var.value) for var in variables)

    # Create sandbox with network enabled for clone
    config = SandboxConfig(network_enabled=True, environment=env_vars)
    sandbox_id = await sandbox_manager.create(config, thread_ref)

    try:
        # Resolve credentials and inject into clone URL if needed
        clone_url, has_ssh_key = await _resolve_credentials(
            state, credential_store, sandbox_manager, sandbox_id, repo_url
        )

        # Build clone command; set GIT_SSH_COMMAND if SSH key was written
        git_prefix = ""
        if has_ssh_key:
            git_prefix = (
                "GIT_SSH_COMMAND='ssh -i /tmp/ssh_key"
                " -o StrictHostKeyChecking=no' "
            )

        # Clone repo into sandbox workspace
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"{git_prefix}git clone --depth=1"
                    f" --branch {repo_branch}"
                    f" {clone_url} /workspace/repo"
                ),
                timeout_seconds=120,
            ),
        )

        # Create and checkout feature branch
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"cd /workspace/repo && git checkout -b {feature_branch}"
                ),
                timeout_seconds=30,
            ),
        )

        # Clone additional repos (if multi-repo project)
        additional_repos = [u for u in repo_urls[1:] if u] if len(repo_urls) > 1 else []
        for idx, extra_url in enumerate(additional_repos, start=1):
            extra_clone_url = extra_url
            if credential_store is not None:
                extra_clone_url, _ = await _resolve_credentials(
                    state, credential_store, sandbox_manager, sandbox_id, extra_url,
                )
            target = f"/workspace/repo-{idx}"
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=(
                        f"{git_prefix}git clone --depth=1"
                        f" --branch {repo_branch}"
                        f" {extra_clone_url} {target}"
                    ),
                    timeout_seconds=120,
                ),
            )
            logger.info(
                "additional_repo_cloned index=%d target=%s url=%s",
                idx,
                target,
                extra_url,
            )

        # Disconnect network now that clone is complete
        await sandbox_manager.disconnect_network(sandbox_id)

        logger.info(
            "workspace_setup_complete sandbox_id=%s repo_url=%s"
            " feature_branch=%s work_item_id=%s audit_action=workspace_cloned",
            sandbox_id,
            repo_url,
            feature_branch,
            work_item_id,
        )
        # TODO: emit AuditEntry when store injection is available

        await mark_completed(_config, "setup_workspace", state)
        return {
            "sandbox_id": sandbox_id,
            "feature_branch": feature_branch,
            "current_phase": "planning",
        }
    except Exception:
        logger.exception("workspace_setup_failed")
        await mark_completed(_config, "setup_workspace", state, error="Workspace setup failed")
        await sandbox_manager.destroy(sandbox_id)
        return {
            "sandbox_id": None,
            "error": "Failed to set up workspace",
            "current_phase": "closed",
        }
