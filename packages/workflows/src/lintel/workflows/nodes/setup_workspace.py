"""Setup workspace node — clones repo into sandbox and creates feature branch."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langchain_core.runnables import RunnableConfig

    from lintel.persistence.protocols import CredentialStore
    from lintel.sandbox.protocols import SandboxManager
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


def _get_claude_code_credentials_json() -> str:
    """Extract Claude Code credentials JSON from macOS Keychain.

    Returns the full credentials JSON string, or empty string if not found.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


async def _inject_claude_credentials(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    credentials_json: str,
) -> None:
    """Write Claude Code credentials and settings into the sandbox.

    Skips writing if credentials already exist (e.g. via bind mount from host).
    """
    from lintel.sandbox.types import SandboxJob

    # Check if credentials token file already exists (not just account info)
    check = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=(
                "test -f /home/vscode/.claude/credentials.json"
                " || test -f /home/vscode/.claude/.credentials.json"
            ),
            timeout_seconds=5,
        ),
    )
    if check.exit_code == 0:
        logger.info(
            "claude_credentials_already_present",
            sandbox=sandbox_id[:12],
        )
        return

    logger.info(
        "injecting_claude_credentials",
        sandbox=sandbox_id[:12],
        creds_len=len(credentials_json),
    )

    # Create ~/.claude directory
    await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(command="mkdir -p /home/vscode/.claude", timeout_seconds=5),
    )

    # Write credentials file
    await sandbox_manager.write_file(
        sandbox_id,
        "/home/vscode/.claude/.credentials.json",
        credentials_json,
    )

    # Write minimal settings that skip interactive permissions
    settings = '{"permissions":{"allow":[],"deny":[]},"hasCompletedOnboarding":true}'
    await sandbox_manager.write_file(
        sandbox_id,
        "/home/vscode/.claude/settings.json",
        settings,
    )

    # Copy ~/.claude.json (account config) into sandbox as a writable file
    # instead of bind-mounting it read-only (which Claude Code tries to update,
    # causing "corrupted config" errors).
    import os

    host_claude_json = os.path.expanduser("~/.claude.json")
    if os.path.isfile(host_claude_json):
        with open(host_claude_json) as f:
            claude_json_content = f.read()
        await sandbox_manager.write_file(
            sandbox_id,
            "/home/vscode/.claude.json",
            claude_json_content,
        )
        logger.info("claude_json_copied_to_sandbox", sandbox=sandbox_id[:12])


def _get_claude_code_oauth_token() -> str:
    """Extract Claude Code OAuth token from macOS Keychain or credentials file.

    Returns the access token string, or empty string if not found.
    """
    import json
    import os
    import subprocess

    # Try macOS Keychain first (newer Claude Code versions)
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            token: str = str(data.get("claudeAiOauth", {}).get("accessToken", ""))
            if token:
                return token
    except (json.JSONDecodeError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Fall back to ~/.claude/.credentials.json (older versions)
    creds_path = os.path.expanduser("~/.claude/.credentials.json")
    try:
        with open(creds_path) as f:
            data = json.loads(f.read())
        token = str(data.get("claudeAiOauth", {}).get("accessToken", ""))
        if token:
            return token
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass

    return ""


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
            from lintel.sandbox.types import SandboxJob

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
    from lintel.contracts.types import ThreadRef
    from lintel.domain.types import Variable  # noqa: TC001
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config)
    _configurable = config.get("configurable", {})
    app_state = _configurable.get("app_state")
    sandbox_manager: SandboxManager | None = _configurable.get("sandbox_manager")
    credential_store: CredentialStore | None = _configurable.get("credential_store") or (
        getattr(app_state, "credential_store", None) if app_state else None
    )
    variable_store = _configurable.get("variable_store") or (
        getattr(app_state, "variable_store", None) if app_state else None
    )

    await tracker.mark_running("setup_workspace")
    await tracker.append_log("setup_workspace", "Setting up workspace...")

    if sandbox_manager is None:
        await tracker.mark_completed("setup_workspace", error="No sandbox manager available")
        msg = "No sandbox manager available — cannot set up workspace"
        raise RuntimeError(msg)

    repo_url = state.get("repo_url", "")
    repo_urls: tuple[str, ...] = state.get("repo_urls", ())
    repo_branch = state.get("repo_branch", "main")
    feature_branch = state.get("feature_branch", "")
    work_item_id = state.get("work_item_id", "")

    # Reuse branch from previous pipeline run (stored on work item)
    if not feature_branch and work_item_id:
        app_state = _configurable.get("app_state")
        wi_store = getattr(app_state, "work_item_store", None) if app_state else None
        if wi_store is not None:
            try:
                wi = await wi_store.get(work_item_id)
                if wi is not None:
                    bn = (
                        wi.get("branch_name", "")
                        if isinstance(wi, dict)
                        else getattr(wi, "branch_name", "")
                    )
                    if bn:
                        feature_branch = bn
                        logger.info("setup_workspace_reusing_branch", branch=bn)
            except Exception:
                logger.warning("setup_workspace_branch_lookup_failed", exc_info=True)
    run_id = state.get("run_id", "")

    # Each pipeline run gets its own directory so runs don't collide
    workspace_root = f"/workspace/{run_id}" if run_id else "/workspace/default"
    repo_path = f"{workspace_root}/repo"

    if not repo_url:
        # No repo configured — acquire a sandbox from the pool so downstream
        # nodes (research, plan, implement) can still operate on the user's request
        await tracker.append_log(
            "setup_workspace", "No repository URL — acquiring sandbox from pool"
        )

        sandbox_store = getattr(app_state, "sandbox_store", None)
        pool_sandbox_id = ""
        if sandbox_store is not None:
            existing = await sandbox_store.list_all()
            free = [s for s in existing if not s.get("pipeline_id")]
            if free:
                pool_sandbox_id = free[0].get("sandbox_id", "")

        if not pool_sandbox_id:
            from lintel.sandbox.errors import NoSandboxAvailableError

            error_msg = (
                "No sandbox available in pool. "
                "Pre-provision sandboxes via the API or wait for one to be released."
            )
            await tracker.append_log("setup_workspace", error_msg)
            await tracker.mark_completed("setup_workspace", error=error_msg)
            raise NoSandboxAvailableError from None

        # Verify the container still exists
        try:
            await sandbox_manager.get_status(pool_sandbox_id)
        except Exception:
            from lintel.sandbox.errors import NoSandboxAvailableError

            logger.warning("pool_sandbox_stale id=%s", pool_sandbox_id[:12])
            error_msg = (
                "No sandbox available in pool. "
                "Pre-provision sandboxes via the API or wait for one to be released."
            )
            await tracker.append_log("setup_workspace", error_msg)
            await tracker.mark_completed("setup_workspace", error=error_msg)
            raise NoSandboxAvailableError from None

        sandbox_id = pool_sandbox_id

        # Allocate to this pipeline
        run_id_val = state.get("run_id", "")
        if sandbox_store is not None and run_id_val:
            try:
                entry = await sandbox_store.get(sandbox_id)
                if entry is not None:
                    entry["pipeline_id"] = run_id_val
                    await sandbox_store.update(sandbox_id, entry)
            except Exception:
                logger.warning("sandbox_allocate_failed", sandbox_id=sandbox_id[:12])

        await sandbox_manager.reconnect_network(sandbox_id)
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command="rm -rf /workspace/*", workdir="/workspace"),
        )
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=f"mkdir -p {repo_path}", timeout_seconds=10),
        )
        # Inject Claude Code credentials so downstream nodes can use the CLI
        credentials_json = _get_claude_code_credentials_json()
        if credentials_json:
            await _inject_claude_credentials(sandbox_manager, sandbox_id, credentials_json)
            await tracker.append_log(
                "setup_workspace", "Claude Code credentials injected into sandbox"
            )
        await tracker.append_log(
            "setup_workspace",
            f"Using sandbox `{sandbox_id[:12]}` from pool (no repo)",
        )
        await tracker.mark_completed(
            "setup_workspace",
            outputs={
                "sandbox_id": sandbox_id,
                "repo_url": "",
                "feature_branch": feature_branch or "lintel/task/work",
                "workspace_path": repo_path,
            },
        )
        return {
            "sandbox_id": sandbox_id,
            "feature_branch": feature_branch or "lintel/task/work",
            "workspace_path": repo_path,
            "current_phase": "planning",
        }

    if not feature_branch:
        from lintel.workflows.nodes._branch_naming import BranchNaming

        intent = state.get("intent", "feature")
        description = ""
        messages = state.get("sanitized_messages", [])
        if messages:
            description = messages[0][:60] if isinstance(messages[0], str) else ""
        feature_branch = (
            BranchNaming.generate(work_item_id, work_type=intent, description=description)
            if work_item_id
            else "lintel/task/work"
        )

    # Parse thread ref
    thread_ref_str = state["thread_ref"]
    parts = thread_ref_str.replace("thread:", "").split(":")
    _thread_ref = ThreadRef(
        workspace_id=parts[0] if len(parts) > 0 else "",
        channel_id=parts[1] if len(parts) > 1 else "",
        thread_ts=parts[2] if len(parts) > 2 else "",
    )

    # Resolve environment variables if environment_id is set
    _env_vars: frozenset[tuple[str, str]] = frozenset()
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
        _env_vars = frozenset(plain)

    # Pick an available sandbox from the pool — fail if none available
    sandbox_store = getattr(app_state, "sandbox_store", None)
    sandbox_id = ""

    if sandbox_store is not None:
        existing = await sandbox_store.list_all()
        # Filter to sandboxes not already allocated to a pipeline
        free = [s for s in existing if not s.get("pipeline_id")]
        total = len(existing)
        await tracker.append_log(
            "setup_workspace",
            f"Found {total} sandbox(es) in pool ({len(free)} free)",
        )
        if free:
            sandbox_id = free[0].get("sandbox_id", "")

    # Check for Claude Code OAuth token (determines network policy)
    oauth_token = _get_claude_code_oauth_token()
    credentials_json = _get_claude_code_credentials_json()
    logger.info(
        "claude_credentials_fetched",
        creds_len=len(credentials_json),
        oauth_len=len(oauth_token),
    )

    if sandbox_id:
        # Verify the sandbox container still exists before using it
        try:
            await sandbox_manager.get_status(sandbox_id)
        except Exception:
            logger.warning("pool_sandbox_stale id=%s", sandbox_id[:12])
            sandbox_id = ""

    if sandbox_id:
        # Mark sandbox as allocated to this pipeline
        run_id = state.get("run_id", "")
        if sandbox_store is not None and run_id:
            try:
                entry = await sandbox_store.get(sandbox_id)
                if entry is not None:
                    entry["pipeline_id"] = run_id
                    await sandbox_store.update(sandbox_id, entry)
            except Exception:
                logger.warning("sandbox_allocate_failed", sandbox_id=sandbox_id[:12])
        # Reconnect network — previous run may have disconnected it
        await sandbox_manager.reconnect_network(sandbox_id)
        # Clean workspace from previous runs to avoid "No space left on device"
        await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command="rm -rf /workspace/*", workdir="/workspace"),
        )
        # Inject Claude Code credentials into reused sandbox
        if credentials_json:
            await _inject_claude_credentials(sandbox_manager, sandbox_id, credentials_json)
        await tracker.append_log(
            "setup_workspace",
            f"Using existing sandbox `{sandbox_id[:12]}` from pool (network reconnected)",
        )
    else:
        from lintel.sandbox.errors import NoSandboxAvailableError

        error_msg = (
            "No sandbox available in pool. "
            "Pre-provision sandboxes via the API or wait for one to be released."
        )
        await tracker.append_log("setup_workspace", error_msg)
        await tracker.mark_completed("setup_workspace", error=error_msg)
        raise NoSandboxAvailableError

    try:
        # Inject secret variables as files in /run/secrets/
        if secret_vars:
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(command="mkdir -p /run/secrets", timeout_seconds=10),
            )
            for var in secret_vars:
                await sandbox_manager.write_file(sandbox_id, f"/run/secrets/{var.key}", var.value)
            await tracker.append_log(
                "setup_workspace",
                f"Injected {len(secret_vars)} secret(s) into sandbox",
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
            await tracker.append_log(
                "setup_workspace", f"Repo already cloned, resetting to {repo_branch} and pulling..."
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
                await tracker.append_log(
                    "setup_workspace",
                    f"Reset failed (exit {reset_result.exit_code}): {reset_result.stderr}",
                )
                # Fall through to re-clone below
                await tracker.append_log("setup_workspace", "Removing stale repo and re-cloning...")
                await sandbox_manager.execute(
                    sandbox_id,
                    SandboxJob(command=f"rm -rf {repo_path}", timeout_seconds=30),
                )
                repo_already_cloned = False
            else:
                await tracker.append_log("setup_workspace", "Repo updated to latest")

        if not repo_already_cloned:
            # Clone repo into sandbox workspace
            await tracker.append_log(
                "setup_workspace", f"Cloning {repo_url} (branch: {repo_branch})..."
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
                await tracker.append_log("setup_workspace", error_msg)
                await tracker.mark_completed("setup_workspace", error=error_msg)
                raise RuntimeError(error_msg)
            await tracker.append_log("setup_workspace", "Clone successful")

        # Verify the repo exists in the sandbox
        verify_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command=f"ls {repo_path}", timeout_seconds=10),
        )
        if verify_result.exit_code != 0:
            error_msg = f"Repo not found at {repo_path} after clone/reset"
            await tracker.append_log("setup_workspace", error_msg)
            await tracker.mark_completed("setup_workspace", error=error_msg)
            raise RuntimeError(error_msg)
        await tracker.append_log(
            "setup_workspace", f"Repo verified: {verify_result.stdout.strip()[:200]}"
        )

        # Create or checkout feature branch (reuse remote branch if it exists)
        await tracker.append_log("setup_workspace", f"Setting up branch: {feature_branch}")
        branch_result = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"cd {repo_path}"
                    f" && git fetch origin {feature_branch} 2>/dev/null"
                    f" && git checkout {feature_branch} 2>/dev/null"
                    f" || git checkout -b {feature_branch}"
                ),
                timeout_seconds=30,
            ),
        )
        if branch_result.exit_code != 0:
            await tracker.append_log(
                "setup_workspace",
                f"Branch setup failed (exit {branch_result.exit_code}): {branch_result.stderr}",
            )
        else:
            # Log whether we reused an existing branch
            out = branch_result.stdout + branch_result.stderr
            if "already exists" in out or "Switched to branch" in out:
                await tracker.append_log(
                    "setup_workspace", f"Reusing existing branch: {feature_branch}"
                )
            else:
                await tracker.append_log("setup_workspace", f"Created new branch: {feature_branch}")

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

        # Install project dependencies while network is still available
        await _install_project_deps(sandbox_manager, sandbox_id, repo_path, config, state)

        # Disconnect network now that clone and deps are complete
        # Keep network active when Claude Code is the provider (needs Anthropic API)
        if not oauth_token:
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

        # Update work item with feature branch so re-dispatch reuses it
        work_item_store = _configurable.get("app_state")
        if work_item_store is not None:
            work_item_store = getattr(work_item_store, "work_item_store", None)
        if work_item_store is not None and work_item_id:
            try:
                item = await work_item_store.get(work_item_id)
                if item is not None:
                    if isinstance(item, dict):
                        item["branch_name"] = feature_branch
                    else:
                        from dataclasses import replace as _replace

                        item = _replace(item, branch_name=feature_branch)
                    await work_item_store.update(work_item_id, item)
                    await tracker.append_log(
                        "setup_workspace", f"Work item updated with branch: {feature_branch}"
                    )
            except Exception:
                logger.warning("setup_workspace_update_work_item_failed", exc_info=True)

        await tracker.mark_completed(
            "setup_workspace",
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
        await tracker.mark_completed("setup_workspace", error="Workspace setup failed")
        raise


async def _install_project_deps(
    sandbox_manager: SandboxManager,
    sandbox_id: str,
    workdir: str,
    config: Mapping[str, Any],
    state: ThreadWorkflowState,
) -> None:
    """Detect project type and install dependencies while network is available."""
    from lintel.sandbox.types import SandboxJob
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config, state)

    detect = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command=f"ls {workdir}/pyproject.toml {workdir}/package.json 2>/dev/null || true",
            workdir=workdir,
            timeout_seconds=10,
        ),
    )
    files = detect.stdout.strip()

    if "pyproject.toml" in files:
        await tracker.append_log("setup_workspace", "Installing Python dependencies...")
        # Ensure uv is on PATH
        uv_check = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command="which uv 2>/dev/null || echo MISSING",
                workdir=workdir,
                timeout_seconds=10,
            ),
        )
        if "MISSING" in uv_check.stdout:
            await tracker.append_log("setup_workspace", "Installing uv...")
            install = await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command="curl -LsSf https://astral.sh/uv/install.sh | sh",
                    workdir=workdir,
                    timeout_seconds=60,
                ),
            )
            if install.exit_code != 0:
                await tracker.append_log(
                    "setup_workspace", f"uv install failed: {install.stderr[:200]}"
                )
                return

        # Deps are pre-cached in the sandbox image (~/.cache/uv), so uv sync
        # links from cache instead of downloading — typically completes in <10s.
        sync = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    'export PATH="$HOME/.local/bin:$PATH" && uv sync --all-extras 2>&1 | tail -5'
                ),
                workdir=workdir,
                timeout_seconds=300,
            ),
        )
        if sync.exit_code == 0:
            await tracker.append_log("setup_workspace", "Python dependencies installed")
            # Download spacy model into venv (presidio needs it at import time)
            await sandbox_manager.execute(
                sandbox_id,
                SandboxJob(
                    command=(
                        'export PATH="$HOME/.local/bin:$PATH" '
                        "&& uv run python -m spacy download en_core_web_sm 2>&1 | tail -3"
                    ),
                    workdir=workdir,
                    timeout_seconds=60,
                ),
            )
        else:
            await tracker.append_log(
                "setup_workspace",
                f"Dependency install failed (non-fatal): {sync.stderr[:200]}",
            )

    elif "package.json" in files:
        await tracker.append_log("setup_workspace", "Installing Node dependencies...")
        npm = await sandbox_manager.execute(
            sandbox_id,
            SandboxJob(command="npm install 2>&1 | tail -5", workdir=workdir, timeout_seconds=120),
        )
        if npm.exit_code == 0:
            await tracker.append_log("setup_workspace", "Node dependencies installed")
        else:
            await tracker.append_log(
                "setup_workspace",
                f"npm install failed (non-fatal): {npm.stderr[:200]}",
            )
