"""Tests for codebase context gathering."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes._codebase_context import gather_codebase_context


def _sandbox_with_tree(tree_output: str = "", grep_output: str = "") -> AsyncMock:
    """Create a mock sandbox that returns tree output and optional grep."""
    sandbox = AsyncMock()

    async def mock_execute(_sid: str, job: object) -> SandboxResult:
        cmd = getattr(job, "command", "")
        if "test -d" in cmd:
            return SandboxResult(exit_code=0, stdout="EXISTS", stderr="")
        if "tree" in cmd:
            return SandboxResult(exit_code=0, stdout=tree_output, stderr="")
        if "ls -R" in cmd:
            return SandboxResult(exit_code=0, stdout=tree_output, stderr="")
        if "grep" in cmd:
            return SandboxResult(exit_code=0, stdout=grep_output, stderr="")
        return SandboxResult(exit_code=0, stdout="", stderr="")

    sandbox.execute.side_effect = mock_execute
    sandbox.read_file.side_effect = FileNotFoundError
    return sandbox


class TestGatherCodebaseContext:
    async def test_returns_directory_tree(self) -> None:
        sandbox = _sandbox_with_tree(".\n├── src/\n│   └── main.py\n└── tests/")

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "Directory Structure" in result
        assert "src/" in result
        assert "main.py" in result

    async def test_falls_back_to_ls_when_tree_missing(self) -> None:
        sandbox = AsyncMock()
        call_count = 0

        async def mock_execute(_sid: str, job: object) -> SandboxResult:
            nonlocal call_count
            cmd = getattr(job, "command", "")
            if "test -d" in cmd:
                return SandboxResult(exit_code=0, stdout="EXISTS", stderr="")
            if "tree" in cmd:
                return SandboxResult(exit_code=0, stdout="", stderr="")
            if "ls -R" in cmd:
                return SandboxResult(exit_code=0, stdout="src:\nmain.py\nutils.py", stderr="")
            return SandboxResult(exit_code=0, stdout="", stderr="")

        sandbox.execute.side_effect = mock_execute
        sandbox.read_file.side_effect = FileNotFoundError

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "Directory Structure" in result
        assert "main.py" in result

    async def test_includes_readme(self) -> None:
        sandbox = _sandbox_with_tree(".")

        async def mock_read_file(_sid: str, path: str) -> str:
            if path.endswith("README.md"):
                return "# My Project\n\nA cool project."
            raise FileNotFoundError

        sandbox.read_file.side_effect = mock_read_file

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "README.md" in result
        assert "A cool project" in result

    async def test_includes_pyproject(self) -> None:
        sandbox = _sandbox_with_tree(".")

        async def mock_read_file(_sid: str, path: str) -> str:
            if path.endswith("pyproject.toml"):
                return '[project]\nname = "myproject"\nversion = "1.0"'
            raise FileNotFoundError

        sandbox.read_file.side_effect = mock_read_file

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "pyproject.toml" in result
        assert 'name = "myproject"' in result

    async def test_truncates_large_files(self) -> None:
        sandbox = _sandbox_with_tree(".")

        async def mock_read_file(_sid: str, path: str) -> str:
            if path.endswith("README.md"):
                return "x" * 5000
            raise FileNotFoundError

        sandbox.read_file.side_effect = mock_read_file

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "... (truncated)" in result

    async def test_includes_grep_patterns(self) -> None:
        grep_out = "src/main.py:1:def main():\nsrc/app.py:5:if __name__"
        sandbox = _sandbox_with_tree(".", grep_output=grep_out)

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "Entry points" in result
        assert "def main():" in result

    async def test_grep_strips_repo_path(self) -> None:
        grep_out = "/workspace/repo/src/app.py:10:@router.get"
        sandbox = _sandbox_with_tree(".", grep_output=grep_out)

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert "/workspace/repo/" not in result
        assert "src/app.py:10" in result

    async def test_returns_empty_when_repo_exists_but_nothing_found(self) -> None:
        """When repo dir exists but has no recognisable content, return empty."""
        sandbox = AsyncMock()

        async def mock_execute(_sid: str, job: object) -> SandboxResult:
            cmd = getattr(job, "command", "")
            if "test -d" in cmd:
                return SandboxResult(exit_code=0, stdout="EXISTS", stderr="")
            return SandboxResult(exit_code=0, stdout="", stderr="")

        sandbox.execute.side_effect = mock_execute
        sandbox.read_file.side_effect = FileNotFoundError

        result = await gather_codebase_context(sandbox, "sandbox-1")

        assert result == ""

    async def test_raises_when_repo_not_found(self) -> None:
        """When the repo directory doesn't exist, raise FileNotFoundError."""
        sandbox = AsyncMock()

        async def mock_execute(_sid: str, job: object) -> SandboxResult:
            cmd = getattr(job, "command", "")
            if "test -d" in cmd:
                return SandboxResult(exit_code=1, stdout="", stderr="")
            return SandboxResult(exit_code=0, stdout="", stderr="")

        sandbox.execute.side_effect = mock_execute
        sandbox.read_file.side_effect = FileNotFoundError

        import pytest

        with pytest.raises(FileNotFoundError, match="Repository not found"):
            await gather_codebase_context(sandbox, "sandbox-1")

    async def test_handles_sandbox_errors_gracefully(self) -> None:
        """When the sandbox is unreachable, the repo check fails and raises."""
        sandbox = AsyncMock()
        sandbox.execute.side_effect = Exception("sandbox down")
        sandbox.read_file.side_effect = Exception("sandbox down")

        import pytest

        with pytest.raises(FileNotFoundError, match="Repository not found"):
            await gather_codebase_context(sandbox, "sandbox-1")
