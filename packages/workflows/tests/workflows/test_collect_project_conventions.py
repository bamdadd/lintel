"""Tests for collect_project_conventions utility and its integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from lintel.sandbox.types import SandboxJob, SandboxResult
from lintel.workflows.nodes.setup_workspace import (
    _MAX_CONVENTIONS_CHARS,
    collect_project_conventions,
)

# ---------------------------------------------------------------------------
# Minimal fake sandbox manager
# ---------------------------------------------------------------------------


class FakeSandboxManager:
    """Sandbox manager stub that returns scripted responses."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        """``responses`` maps *substring of command* → stdout string."""
        self._responses: dict[str, str] = responses or {}
        self.executed: list[str] = []

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        self.executed.append(job.command)
        for pattern, output in self._responses.items():
            if pattern in job.command:
                return SandboxResult(exit_code=0, stdout=output)
        return SandboxResult(exit_code=0, stdout="")


# ---------------------------------------------------------------------------
# collect_project_conventions tests
# ---------------------------------------------------------------------------


class TestCollectProjectConventions:
    async def test_returns_empty_when_no_claude_md(self) -> None:
        manager = FakeSandboxManager({"find": ""})

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert result == ""

    async def test_returns_root_claude_md_content(self) -> None:
        manager = FakeSandboxManager(
            {
                "find": "./CLAUDE.md\n",
                "cat ./CLAUDE.md": "# Project Rules\nUse ruff for linting.\n",
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert "Project Rules" in result
        assert "ruff" in result

    async def test_root_claude_md_comes_first(self) -> None:
        manager = FakeSandboxManager(
            {
                "find": "./packages/foo/CLAUDE.md\n./CLAUDE.md\n",
                "cat ./CLAUDE.md": "Root conventions.\n",
                "cat ./packages/foo/CLAUDE.md": "Package foo conventions.\n",
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        root_pos = result.index("Root conventions")
        nested_pos = result.index("Package foo conventions")
        assert root_pos < nested_pos

    async def test_multiple_files_concatenated(self) -> None:
        manager = FakeSandboxManager(
            {
                "find": "./CLAUDE.md\n./packages/bar/CLAUDE.md\n",
                "cat ./CLAUDE.md": "Root.\n",
                "cat ./packages/bar/CLAUDE.md": "Bar package.\n",
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert "Root." in result
        assert "Bar package." in result

    async def test_respects_max_chars_limit(self) -> None:
        # Build a CLAUDE.md that is larger than the cap
        large_content = "x" * (_MAX_CONVENTIONS_CHARS + 5000)
        manager = FakeSandboxManager(
            {
                "find": "./CLAUDE.md\n",
                "cat ./CLAUDE.md": large_content,
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert len(result) <= _MAX_CONVENTIONS_CHARS + 50  # allow small header/trailer overhead
        assert "truncated" in result

    async def test_skips_empty_files(self) -> None:
        manager = FakeSandboxManager(
            {
                "find": "./CLAUDE.md\n",
                "cat ./CLAUDE.md": "   \n",
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert result == ""

    async def test_handles_find_error_gracefully(self) -> None:
        """A failing find command should not raise — return empty string."""
        manager = FakeSandboxManager()

        async def raise_on_execute(sandbox_id: str, job: SandboxJob) -> SandboxResult:
            msg = "sandbox error"
            raise RuntimeError(msg)

        manager.execute = raise_on_execute  # type: ignore[assignment]

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert result == ""

    async def test_includes_file_path_header(self) -> None:
        manager = FakeSandboxManager(
            {
                "find": "./CLAUDE.md\n",
                "cat ./CLAUDE.md": "Some content.\n",
            }
        )

        result = await collect_project_conventions(manager, "sbx-1", "/workspace/repo")

        assert "./CLAUDE.md" in result


# ---------------------------------------------------------------------------
# Integration: setup_workspace stores project_conventions in returned state
# ---------------------------------------------------------------------------


class TestSetupWorkspaceConventions:
    """Verify setup_workspace returns project_conventions in its state dict."""

    @pytest.fixture(autouse=True)
    def _patch_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lintel.workflows.nodes.setup_workspace._get_claude_code_credentials_json",
            lambda: "",
        )
        monkeypatch.setattr(
            "lintel.workflows.nodes.setup_workspace._get_claude_code_oauth_token",
            lambda: "",
        )

    async def test_project_conventions_in_returned_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """setup_workspace should include project_conventions from collected CLAUDE.md."""
        from lintel.sandbox.types import SandboxResult
        from lintel.workflows.nodes.setup_workspace import setup_workspace

        pool_id = "pool-sbx-42"

        class _SandboxStore:
            async def list_all(self) -> list[dict[str, Any]]:
                return [{"sandbox_id": pool_id}]

            async def get(self, sid: str) -> dict[str, Any] | None:
                return {"sandbox_id": sid} if sid == pool_id else None

            async def update(self, sid: str, data: dict[str, Any]) -> None:
                pass

        class _AppState:
            sandbox_store = _SandboxStore()

        conventions_content = "# CLAUDE.md\nFollow strict TDD.\n"

        async def _execute(sandbox_id: str, job: SandboxJob) -> SandboxResult:
            cmd = job.command
            if "find" in cmd and "CLAUDE.md" in cmd:
                return SandboxResult(exit_code=0, stdout="./CLAUDE.md\n")
            if "cat ./CLAUDE.md" in cmd:
                return SandboxResult(exit_code=0, stdout=conventions_content)
            if "git clone" in cmd:
                return SandboxResult(exit_code=0, stdout="Cloning into ...\n")
            if "git diff" in cmd or "git fetch" in cmd or "git checkout" in cmd:
                return SandboxResult(exit_code=0, stdout="")
            if "test -d" in cmd and ".git" in cmd:
                return SandboxResult(exit_code=1, stdout="")  # not yet cloned
            if "ls " in cmd:
                return SandboxResult(exit_code=0, stdout="README.md\n")
            return SandboxResult(exit_code=0, stdout="")

        manager = AsyncMock()
        manager.execute = _execute
        manager.reconnect_network = AsyncMock()
        manager.disconnect_network = AsyncMock()
        manager.write_file = AsyncMock()

        state: dict[str, Any] = {
            "thread_ref": "thread:W1:C1:1.0",
            "correlation_id": "test-corr",
            "current_phase": "routing",
            "sanitized_messages": ["implement feature"],
            "intent": "feature",
            "plan": {},
            "agent_outputs": [],
            "pending_approvals": [],
            "sandbox_id": None,
            "sandbox_results": [],
            "pr_url": "",
            "error": None,
            "project_id": "proj-1",
            "work_item_id": "wi-99",
            "run_id": "run-42",
            "repo_url": "https://github.com/test/repo.git",
            "repo_branch": "main",
            "feature_branch": "lintel/feat/wi-99",
            "credential_ids": (),
        }
        config: dict[str, Any] = {
            "configurable": {
                "sandbox_manager": manager,
                "app_state": _AppState(),
            }
        }

        result = await setup_workspace(state, config)  # type: ignore[arg-type]

        assert "project_conventions" in result
        assert "TDD" in result["project_conventions"]

    async def test_project_conventions_empty_when_no_claude_md(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no CLAUDE.md exists, project_conventions should be an empty string."""
        from lintel.sandbox.types import SandboxResult
        from lintel.workflows.nodes.setup_workspace import setup_workspace

        pool_id = "pool-sbx-43"

        class _SandboxStore:
            async def list_all(self) -> list[dict[str, Any]]:
                return [{"sandbox_id": pool_id}]

            async def get(self, sid: str) -> dict[str, Any] | None:
                return {"sandbox_id": sid} if sid == pool_id else None

            async def update(self, sid: str, data: dict[str, Any]) -> None:
                pass

        class _AppState:
            sandbox_store = _SandboxStore()

        async def _execute(sandbox_id: str, job: SandboxJob) -> SandboxResult:
            cmd = job.command
            if "find" in cmd and "CLAUDE.md" in cmd:
                return SandboxResult(exit_code=0, stdout="")  # no CLAUDE.md files
            if "git clone" in cmd:
                return SandboxResult(exit_code=0, stdout="Cloning...\n")
            if "git diff" in cmd or "git fetch" in cmd or "git checkout" in cmd:
                return SandboxResult(exit_code=0, stdout="")
            if "test -d" in cmd and ".git" in cmd:
                return SandboxResult(exit_code=1, stdout="")
            if "ls " in cmd:
                return SandboxResult(exit_code=0, stdout="README.md\n")
            return SandboxResult(exit_code=0, stdout="")

        manager = AsyncMock()
        manager.execute = _execute
        manager.reconnect_network = AsyncMock()
        manager.disconnect_network = AsyncMock()
        manager.write_file = AsyncMock()

        state: dict[str, Any] = {
            "thread_ref": "thread:W1:C1:1.0",
            "correlation_id": "test-corr",
            "current_phase": "routing",
            "sanitized_messages": ["implement feature"],
            "intent": "feature",
            "plan": {},
            "agent_outputs": [],
            "pending_approvals": [],
            "sandbox_id": None,
            "sandbox_results": [],
            "pr_url": "",
            "error": None,
            "project_id": "proj-1",
            "work_item_id": "wi-98",
            "run_id": "run-43",
            "repo_url": "https://github.com/test/repo.git",
            "repo_branch": "main",
            "feature_branch": "lintel/feat/wi-98",
            "credential_ids": (),
        }
        config: dict[str, Any] = {
            "configurable": {
                "sandbox_manager": manager,
                "app_state": _AppState(),
            }
        }

        result = await setup_workspace(state, config)  # type: ignore[arg-type]

        assert result.get("project_conventions", "") == ""
