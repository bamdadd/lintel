"""Tests for the discover_test_command skill."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.contracts.types import SandboxResult
from lintel.skills.discover_test_command import (
    DiscoverTestCommandSkill,
    discover_test_command,
    pick_test_target,
)


def _mock_sandbox(
    *results: tuple[int, str, str],
) -> AsyncMock:
    mgr = AsyncMock()
    side_effects = [SandboxResult(exit_code=ec, stdout=out, stderr=err) for ec, out, err in results]
    mgr.execute = AsyncMock(side_effect=side_effects)
    return mgr


class TestDiscoverTestCommand:
    async def test_makefile_with_make_help(self) -> None:
        mgr = _mock_sandbox(
            # detect files
            (0, "/workspace/repo/Makefile\n/workspace/repo/pyproject.toml", ""),
            # make help
            (0, "test         Run all tests\nlint         Lint code\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert result["test_command"] == "make test"
        # Python project detected, should have setup commands
        assert len(result["setup_commands"]) > 0

    async def test_makefile_fallback_to_grep_targets(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Makefile", ""),
            # make help — empty
            (0, "", ""),
            # grep targets
            (0, "build\ntest\nclean\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert result["test_command"] == "make test"

    async def test_package_json_with_test_script(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/package.json", ""),
            (0, "HAS_TEST", ""),  # grep for test script
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert result["test_command"] == "npm test"
        assert "npm install" in result["setup_commands"]

    async def test_pyproject_toml(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/pyproject.toml", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert "pytest" in result["test_command"]
        assert len(result["setup_commands"]) > 0

    async def test_cargo_toml(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Cargo.toml", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert result["test_command"] == "cargo test"
        assert result["setup_commands"] == []

    async def test_go_mod(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/go.mod", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert result["test_command"] == "go test ./..."

    async def test_no_recognizable_project(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),  # no files found
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        assert "No test runner" in result["test_command"]

    async def test_makefile_no_test_target_falls_through(self) -> None:
        """Makefile exists but has no test-like target → falls through."""
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Makefile\n/workspace/repo/Cargo.toml", ""),
            # make help — no test target
            (0, "build\ndeploy\n", ""),
            # grep targets — still no test target
            (0, "build\ndeploy\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        # Falls through to Cargo.toml detection
        assert result["test_command"] == "cargo test"

    async def test_package_json_without_test_script(self) -> None:
        """package.json exists but has no test script → falls through."""
        mgr = _mock_sandbox(
            (0, "/workspace/repo/package.json\n/workspace/repo/go.mod", ""),
            (0, "", ""),  # grep — no HAS_TEST
        )
        result = await discover_test_command(mgr, "sb-1", "/workspace/repo")

        # Falls through to go.mod
        assert result["test_command"] == "go test ./..."


class TestPickTestTarget:
    def test_prefers_test_over_all(self) -> None:
        assert pick_test_target("lint\nall\ntest\nclean") == "test"

    def test_picks_test(self) -> None:
        assert pick_test_target("build\ntest\nclean") == "test"

    def test_picks_check(self) -> None:
        assert pick_test_target("build\ncheck\nclean") == "check"

    def test_returns_none_when_no_match(self) -> None:
        assert pick_test_target("build\nclean\ndeploy") is None

    def test_handles_make_help_format(self) -> None:
        output = "test         Run all tests\nlint         Lint code"
        assert pick_test_target(output) == "test"

    def test_prefers_test_all_over_all(self) -> None:
        assert pick_test_target("test-unit\ntest-all\nall") == "test-all"

    def test_ignores_description_words(self) -> None:
        """'all' in description should not match — only first token counts."""
        output = "lint         Run all linters\nbuild        Build all"
        assert pick_test_target(output) is None


class TestSkillProtocol:
    def test_descriptor_has_correct_fields(self) -> None:
        skill = DiscoverTestCommandSkill()
        desc = skill.descriptor
        assert desc.name == "skill_discover_test_command"
        assert desc.input_schema is not None
        assert "workdir" in str(desc.input_schema)
        assert desc.output_schema is not None

    async def test_execute_returns_result(self) -> None:
        mgr = _mock_sandbox(
            (0, "/workspace/repo/Cargo.toml", ""),
        )
        skill = DiscoverTestCommandSkill()
        result = await skill.execute(
            {"workdir": "/workspace/repo", "sandbox_id": "sb-1"},
            {"sandbox_manager": mgr},
        )
        assert result.success is True
        assert result.output is not None
        assert result.output["test_command"] == "cargo test"

    async def test_execute_fails_without_sandbox(self) -> None:
        skill = DiscoverTestCommandSkill()
        result = await skill.execute(
            {"workdir": "/workspace/repo", "sandbox_id": "sb-1"},
            {},  # no sandbox_manager
        )
        assert result.success is False
        assert result.error is not None
