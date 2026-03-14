"""Tests for the git helper utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.contracts.types import SandboxJob, SandboxResult
from lintel.workflows.nodes._git_helpers import GitOperations, rebase_on_upstream


def _make_sandbox_manager(exit_code: int = 0) -> AsyncMock:
    manager = AsyncMock()
    manager.execute = AsyncMock(
        return_value=SandboxResult(exit_code=exit_code, stdout="ok\n"),
    )
    return manager


class TestRebaseOnUpstream:
    async def test_success(self) -> None:
        manager = _make_sandbox_manager(exit_code=0)

        result = await rebase_on_upstream(manager, "sbx-1", "main")

        assert result["success"] is True
        assert "Rebased successfully" in result["message"]
        # Should have called execute once (just the rebase)
        manager.execute.assert_called_once()
        job: SandboxJob = manager.execute.call_args[0][1]
        assert "git rebase main" in job.command

    async def test_conflict_returns_warning(self) -> None:
        manager = AsyncMock()
        # First call (rebase) fails, second call (abort) succeeds
        manager.execute = AsyncMock(
            side_effect=[
                SandboxResult(exit_code=1, stdout="CONFLICT\n"),
                SandboxResult(exit_code=0, stdout=""),
            ],
        )

        result = await rebase_on_upstream(manager, "sbx-1", "main")

        assert result["success"] is False
        assert "conflicts" in result["message"].lower()
        # Should have called rebase then abort
        assert manager.execute.call_count == 2
        abort_job: SandboxJob = manager.execute.call_args_list[1][0][1]
        assert "rebase --abort" in abort_job.command

    async def test_custom_workdir(self) -> None:
        manager = _make_sandbox_manager(exit_code=0)

        await rebase_on_upstream(manager, "sbx-1", "develop", workdir="/custom/path")

        job: SandboxJob = manager.execute.call_args[0][1]
        assert "cd /custom/path" in job.command
        assert "git rebase develop" in job.command


class TestGitOperations:
    """Tests for the GitOperations class interface."""

    async def test_rebase_success_via_class(self) -> None:
        manager = _make_sandbox_manager(exit_code=0)
        ops = GitOperations(manager, "sbx-1")
        result = await ops.rebase_on_upstream("main")
        assert result["success"] is True
        assert "Rebased successfully" in result["message"]

    async def test_rebase_conflict_via_class(self) -> None:
        manager = AsyncMock()
        manager.execute = AsyncMock(
            side_effect=[
                SandboxResult(exit_code=1, stdout="CONFLICT\n"),
                SandboxResult(exit_code=0, stdout=""),
            ],
        )
        ops = GitOperations(manager, "sbx-1")
        result = await ops.rebase_on_upstream("main")
        assert result["success"] is False
        assert manager.execute.call_count == 2
