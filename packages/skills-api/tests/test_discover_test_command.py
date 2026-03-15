"""Tests for the discover_test_command skill."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.skills_api.domain.discover_test_command import (
    DiscoverTestCommandSkill,
    discover_test_command,
    pick_test_target,
)
from lintel.sandbox.types import SandboxResult


def _mock_sandbox(
    *results: tuple[int, str, str],
) -> AsyncMock:
    mgr = AsyncMock()
    side_effects = [SandboxResult(exit_code=ec, stdout=out, stderr=err) for ec, out, err in results]
    mgr.execute = AsyncMock(side_effect=side_effects)
    return mgr


class TestDiscoverTestCommand:
    async def test_python_with_makefile_and_postgres(self) -> None:
        """Python project with Makefile, postgres available → make test."""
        mgr = _mock_sandbox(
            # detect files
            (0, "/w/Makefile\n/w/pyproject.toml", ""),
            # workspace check
            (0, "0", ""),
            # detect capabilities (postgres available)
            (0, "HAS_POSTGRES\nHAS_UV", ""),
            # _python_setup: probe installed
            (0, "MISSING", ""),
            # _python_setup: which uv
            (0, "/root/.local/bin/uv", ""),
            # _python_setup: workspace check for sync
            (0, "0", ""),
            # _detect_python_extras: grep pyproject.toml
            (0, '"spacy>=3.0"', ""),
            # _python_test_command: make help
            (0, "test         Run all tests\nlint         Lint\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "make test"
        assert len(result["setup_commands"]) >= 2  # uv sync + spacy
        assert any("uv sync" in c for c in result["setup_commands"])
        assert any("spacy" in c for c in result["setup_commands"])

    async def test_python_without_postgres_uses_unit_target(self) -> None:
        """Python project, no postgres → falls back to test-unit."""
        mgr = _mock_sandbox(
            (0, "/w/Makefile\n/w/pyproject.toml", ""),
            (0, "0", ""),  # workspace check
            (0, "HAS_UV", ""),
            # probe installed
            (0, "MISSING", ""),
            (0, "/root/.local/bin/uv", ""),
            (0, "0", ""),  # workspace check for sync
            (0, "", ""),
            # _python_test_command: make help
            (0, "test         Run all\ntest-unit    Unit tests\n", ""),
            # _find_make_unit_target: grep Makefile
            (0, "test\ntest-unit\nlint\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "make test-unit"

    async def test_python_without_makefile(self) -> None:
        """Python project, no Makefile → pytest directly."""
        mgr = _mock_sandbox(
            (0, "/w/pyproject.toml", ""),
            (0, "0", ""),  # workspace check
            (0, "HAS_UV\nHAS_POSTGRES", ""),
            (0, "MISSING", ""),
            (0, "/root/.local/bin/uv", ""),
            (0, "0", ""),  # workspace check for sync
            (0, "", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert "pytest" in result["test_command"]
        assert "tests/unit/" not in result["test_command"]  # postgres is available

    async def test_installs_uv_when_missing(self) -> None:
        """uv not found → setup includes curl install."""
        mgr = _mock_sandbox(
            (0, "/w/pyproject.toml", ""),
            (0, "0", ""),  # workspace check
            (0, "", ""),
            (0, "MISSING", ""),  # probe
            (0, "MISSING", ""),  # which uv
            (0, "0", ""),  # workspace check for sync
            (0, "", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert any("install.sh" in c for c in result["setup_commands"])
        assert any("uv sync" in c for c in result["setup_commands"])

    async def test_skips_setup_when_already_installed(self) -> None:
        """When venv exists with project installed, skip all setup."""
        mgr = _mock_sandbox(
            (0, "/w/Makefile\n/w/pyproject.toml", ""),
            (0, "0", ""),  # workspace check
            (0, "HAS_UV", ""),
            # probe: already installed
            (0, "INSTALLED", ""),
            # _python_test_command: make help
            (0, "test         Run all\ntest-unit    Unit tests\n", ""),
            # _find_make_unit_target
            (0, "test\ntest-unit\nlint\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "make test-unit"
        assert result["setup_commands"] == []

    async def test_workspace_prefers_test_affected(self) -> None:
        """uv workspace with test-affected target → make test-affected."""
        mgr = _mock_sandbox(
            (0, "/w/Makefile\n/w/pyproject.toml", ""),
            (0, "1", ""),  # workspace check → is workspace
            (0, "HAS_UV", ""),
            # probe: already installed
            (0, "INSTALLED", ""),
            # _find_make_affected_target: grep Makefile
            (0, "test\ntest-unit\ntest-affected\nlint\n", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "make test-affected"

    async def test_cargo_toml(self) -> None:
        mgr = _mock_sandbox(
            (0, "/w/Cargo.toml", ""),
            (0, "", ""),  # capabilities
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "cargo test"

    async def test_go_mod(self) -> None:
        mgr = _mock_sandbox(
            (0, "/w/go.mod", ""),
            (0, "", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert result["test_command"] == "go test ./..."

    async def test_no_recognizable_project(self) -> None:
        mgr = _mock_sandbox(
            (0, "", ""),
            (0, "", ""),
        )
        result = await discover_test_command(mgr, "sb-1", "/w")

        assert "No test runner" in result["test_command"]


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
        output = "lint         Run all linters\nbuild        Build all"
        assert pick_test_target(output) is None


class TestSkillProtocol:
    def test_descriptor_has_correct_fields(self) -> None:
        skill = DiscoverTestCommandSkill()
        desc = skill.descriptor
        assert desc.name == "skill_discover_test_command"
        assert desc.input_schema is not None
        assert desc.output_schema is not None

    async def test_execute_returns_result(self) -> None:
        mgr = _mock_sandbox(
            (0, "/w/Cargo.toml", ""),
            (0, "", ""),  # capabilities
        )
        skill = DiscoverTestCommandSkill()
        result = await skill.execute(
            {"workdir": "/w", "sandbox_id": "sb-1"},
            {"sandbox_manager": mgr},
        )
        assert result.success is True
        assert result.output is not None
        assert result.output["test_command"] == "cargo test"

    async def test_execute_fails_without_sandbox(self) -> None:
        skill = DiscoverTestCommandSkill()
        result = await skill.execute(
            {"workdir": "/w", "sandbox_id": "sb-1"},
            {},
        )
        assert result.success is False
        assert result.error is not None
