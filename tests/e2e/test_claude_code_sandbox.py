"""E2E test: Claude Code sandbox with host ~/.claude mount.

Requires:
  - Docker running
  - lintel-sandbox:latest image built (make build-sandbox)
  - ~/.claude directory exists on host

Run with: uv run pytest tests/e2e/test_claude_code_sandbox.py -v
"""

from __future__ import annotations

import os

import pytest

from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef
from lintel.sandbox.docker_backend import DockerSandboxManager

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.path.isdir(os.path.expanduser("~/.claude")),
        reason="~/.claude directory not found on host",
    ),
]


@pytest.fixture()
async def manager() -> DockerSandboxManager:
    return DockerSandboxManager()


@pytest.fixture()
async def sandbox_with_claude(manager: DockerSandboxManager) -> str:
    """Create a sandbox with ~/.claude mounted (mimics claude-code preset)."""
    home = os.environ["HOME"]
    config = SandboxConfig(
        image="lintel-sandbox:latest",
        network_enabled=True,
        mounts=(
            (f"{home}/.claude", "/root/.claude", "bind"),
            (f"{home}/.claude.json", "/root/.claude.json", "bind"),
        ),
    )
    thread_ref = ThreadRef(workspace_id="test", channel_id="e2e", thread_ts="1.0")
    sandbox_id = await manager.create(config, thread_ref)
    yield sandbox_id  # type: ignore[misc]
    await manager.destroy(sandbox_id)


class TestClaudeCodeSandbox:
    async def test_claude_dir_mounted(
        self,
        manager: DockerSandboxManager,
        sandbox_with_claude: str,
    ) -> None:
        """Verify ~/.claude from host is visible inside the container."""
        result = await manager.execute(
            sandbox_with_claude,
            SandboxJob(command="ls /root/.claude/", timeout_seconds=10),
        )
        assert result.exit_code == 0
        assert result.stdout.strip()  # Should contain files

    async def test_claude_cli_available(
        self,
        manager: DockerSandboxManager,
        sandbox_with_claude: str,
    ) -> None:
        """Verify claude CLI is available (baked in or on npm global path)."""
        result = await manager.execute(
            sandbox_with_claude,
            SandboxJob(
                command=(
                    "which claude"
                    " || npm list -g @anthropic-ai/claude-code 2>/dev/null | grep claude"
                ),
                timeout_seconds=15,
            ),
        )
        # Pass if claude is on PATH or npm global package is listed
        assert result.exit_code == 0 or "claude" in result.stdout

    async def test_claude_mount_is_read_only(
        self,
        manager: DockerSandboxManager,
        sandbox_with_claude: str,
    ) -> None:
        """Verify the mount is read-only — agent code cannot modify credentials."""
        result = await manager.execute(
            sandbox_with_claude,
            SandboxJob(
                command="touch /root/.claude/test-write 2>&1; echo $?",
                timeout_seconds=10,
            ),
        )
        # Should fail because mount is read-only
        output = result.stdout.strip()
        assert "1" in output or "Read-only" in result.stderr

    async def test_network_allows_anthropic_api(
        self,
        manager: DockerSandboxManager,
        sandbox_with_claude: str,
    ) -> None:
        """Verify the sandbox can reach Anthropic API (needed for Claude Code)."""
        result = await manager.execute(
            sandbox_with_claude,
            SandboxJob(
                command="curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/",
                timeout_seconds=15,
            ),
        )
        # Any HTTP response (even 404) means network connectivity works
        assert result.exit_code == 0
        http_code = result.stdout.strip()
        assert http_code.isdigit(), f"Expected HTTP status code, got: {http_code}"
