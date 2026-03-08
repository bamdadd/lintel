"""Setup workspace node — clones repo into sandbox and creates feature branch."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.contracts.protocols import CredentialStore, SandboxManager
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
            await sandbox_manager.write_file(sandbox_id, "/tmp/ssh_key", secret)
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="chmod 600 /tmp/ssh_key", timeout_seconds=10),
            )

    return repo_url, has_ssh_key


async def setup_workspace(
    state: ThreadWorkflowState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Clone the project repo into a sandbox and create a feature branch.

    Expects project_id, repo_url, repo_branch, work_item_id, and feature_branch
    to be set in state (populated by the chat route before workflow dispatch).
    """
    from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef, Variable
    from lintel.workflows.nodes._stage_tracking import append_log, mark_completed, mark_running

    _configurable = config.get("configurable", {})
    app_state = _configurable.get("app_state")
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    credential_store: CredentialStore | None = _configurable.get("credential_store") or (
        getattr(app_state, "credential_store", None) if app_state else None
    )
    variable_store = _configurable.get("variable_store") or (
        getattr(app_state, "variable_store", None) if app_state else None
    )

    await mark_running(config, "setup_workspace", state)
    await append_log(config, "setup_workspace", "Setting up workspace...", state)

    if sandbox_manager is None:
        await mark_completed(config, "setup_workspace", state, error="No sandbox manager available")
        msg = "No sandbox manager available — cannot set up workspace"
        raise RuntimeError(msg)

    repo_url = state.get("repo_url", "")
    repo_urls: tuple[str, ...] = state.get("repo_urls", ())
    repo_branch = state.get("repo_branch", "main")
    feature_branch = state.get("feature_branch", "")
    work_item_id = state.get("work_item_id", "")
    run_id = state.get("run_id", "")

    # Each pipeline run gets its own directory so runs don't collide
    workspace_root = f"/workspace/{run_id}" if run_id else "/workspace/default"
    repo_path = f"{workspace_root}/repo"

    if not repo_url:
        await mark_completed(config, "setup_workspace", state, error="No repository URL")
        msg = "No repository URL configured for this project"
        raise RuntimeError(msg)

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
    secret_vars: list[Variable] = []
    environment_id = state.get("environment_id", "")
    if environment_id and variable_store is not None:
        variables = await variable_store.list_all(environment_id=environment_id)
        plain: list[tuple[str, str]] = []
        for var in variables:
            if var.is_secret:
                secret_vars.append(var)
                logger.info(
                    "secret_variable_deferred key=%s environment_id=%s",
                    var.key,
                    environment_id,
                )
            else:
                plain.append((var.key, var.value))
        env_vars = frozenset(plain)

    # Pick an available sandbox from the user-created pool, or create one as fallback
    sandbox_store = getattr(app_state, "sandbox_store", None)
    sandbox_id = ""
    created_sandbox = False

    if sandbox_store is not None:
        existing = await sandbox_store.list_all()
        await append_log(
            config,
            "setup_workspace",
            f"Found {len(existing)} sandbox(es) in pool",
            state,
        )
        if existing:
            sandbox_id = existing[0].get("sandbox_id", "")

    if sandbox_id:
        # Reconnect network — previous run may have disconnected it
        await sandbox_manager.reconnect_network(sandbox_id)
        await append_log(
            config,
            "setup_workspace",
            f"Using existing sandbox `{sandbox_id[:12]}` from pool (network reconnected)",
            state,
        )
    else:
        await append_log(
            config,
            "setup_workspace",
            "No sandboxes in pool — creating a new one (fallback)",
            state,
        )
        sandbox_config = SandboxConfig(network_enabled=True, environment=env_vars)
        sandbox_id = await sandbox_manager.create(sandbox_config, thread_ref)
        created_sandbox = True
        await append_log(
            config,
            "setup_workspace",
            f"Sandbox created: `{sandbox_id[:12]}`",
            state,
        )

    try:
        # Inject secret variables as files in /run/secrets/
        if secret_vars:
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="mkdir -p /run/secrets", timeout_seconds=10),
            )
            for var in secret_vars:
                await sandbox_manager.write_file(sandbox_id, f"/run/secrets/{var.key}", var.value)
            await append_log(
                config,
                "setup_workspace",
                f"Injected {len(secret_vars)} secret(s) into sandbox",
                state,
            )

        # Create the run-specific workspace directory
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=f"mkdir -p {workspace_root}", timeout_seconds=10),
        )

        # Resolve credentials and inject into clone URL if needed
        clone_url, has_ssh_key = await _resolve_credentials(
            state, credential_store, sandbox_manager, sandbox_id, repo_url
        )

        # Build clone command; set GIT_SSH_COMMAND if SSH key was written
        git_prefix = ""
        if has_ssh_key:
            git_prefix = "GIT_SSH_COMMAND='ssh -i /tmp/ssh_key -o StrictHostKeyChecking=no' "

        # Check if repo is already cloned in the sandbox
        repo_check = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=f"test -d {repo_path}/.git && echo EXISTS", timeout_seconds=10),
        )
        repo_already_cloned = "EXISTS" in repo_check.stdout

        if repo_already_cloned:
            # Repo exists — checkout base branch and pull latest
            await append_log(
                config,
                "setup_workspace",
                f"Repo already cloned, resetting to {repo_branch} and pulling...",
                state,
            )
            reset_cmd = (
                f"cd {repo_path}"
                f" && {git_prefix}git fetch origin {repo_branch}"
                f" && git checkout {repo_branch}"
                f" && git reset --hard origin/{repo_branch}"
            )
            reset_result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command=reset_cmd, timeout_seconds=60),
            )
            if reset_result.exit_code != 0:
                await append_log(
                    config,
                    "setup_workspace",
                    f"Reset failed (exit {reset_result.exit_code}): {reset_result.stderr}",
                    state,
                )
                # Fall through to re-clone below
                await append_log(
                    config, "setup_workspace", "Removing stale repo and re-cloning...", state
                )
                await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(command=f"rm -rf {repo_path}", timeout_seconds=30),
                )
                repo_already_cloned = False
            else:
                await append_log(config, "setup_workspace", "Repo updated to latest", state)

        if not repo_already_cloned:
            # Clone repo into sandbox workspace
            await append_log(
                config, "setup_workspace", f"Cloning {repo_url} (branch: {repo_branch})...", state
            )
            clone_result = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=(
                        f"{git_prefix}git clone --depth=1"
                        f" --branch {repo_branch}"
                        f" {clone_url} {repo_path}"
                    ),
                    timeout_seconds=120,
                ),
            )
            if clone_result.exit_code != 0:
                error_msg = (
                    f"Git clone failed (exit {clone_result.exit_code}): {clone_result.stderr}"
                )
                await append_log(config, "setup_workspace", error_msg, state)
                await mark_completed(config, "setup_workspace", state, error=error_msg)
                raise RuntimeError(error_msg)
            await append_log(config, "setup_workspace", "Clone successful", state)

        # Verify the repo exists in the sandbox
        verify_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=f"ls {repo_path}", timeout_seconds=10),
        )
        if verify_result.exit_code != 0:
            error_msg = f"Repo not found at {repo_path} after clone/reset"
            await append_log(config, "setup_workspace", error_msg, state)
            await mark_completed(config, "setup_workspace", state, error=error_msg)
            raise RuntimeError(error_msg)
        await append_log(
            config, "setup_workspace", f"Repo verified: {verify_result.stdout.strip()[:200]}", state
        )

        # Create and checkout feature branch
        await append_log(config, "setup_workspace", f"Creating branch: {feature_branch}", state)
        branch_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=f"cd {repo_path} && git checkout -b {feature_branch}",
                timeout_seconds=30,
            ),
        )
        if branch_result.exit_code != 0:
            await append_log(
                config,
                "setup_workspace",
                f"Branch creation failed (exit {branch_result.exit_code}): {branch_result.stderr}",
                state,
            )

        # Clone additional repos (if multi-repo project)
        additional_repos = [u for u in repo_urls[1:] if u] if len(repo_urls) > 1 else []
        for idx, extra_url in enumerate(additional_repos, start=1):
            extra_clone_url = extra_url
            if credential_store is not None:
                extra_clone_url, _ = await _resolve_credentials(
                    state,
                    credential_store,
                    sandbox_manager,
                    sandbox_id,
                    extra_url,
                )
            target = f"{workspace_root}/repo-{idx}"
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

        await mark_completed(
            config,
            "setup_workspace",
            state,
            outputs={
                "sandbox_id": sandbox_id,
                "repo_url": repo_url,
                "feature_branch": feature_branch,
                "workspace_path": repo_path,
            },
        )
        return {
            "sandbox_id": sandbox_id,
            "feature_branch": feature_branch,
            "workspace_path": repo_path,
            "current_phase": "planning",
        }
    except Exception:
        logger.exception("workspace_setup_failed")
        await mark_completed(config, "setup_workspace", state, error="Workspace setup failed")
        if created_sandbox:
            await sandbox_manager.destroy(sandbox_id)
        raise
