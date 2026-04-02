"""Tests for the affected-test selection module."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.sandbox.types import SandboxResult
from lintel.workflows.nodes._affected_tests import (
    AffectedTestResult,
    build_pytest_command,
    detect_changed_files,
    parse_test_results_per_module,
    select_affected_tests,
)


def _mock_sandbox(*results: tuple[int, str]) -> AsyncMock:
    mgr = AsyncMock()
    mgr.execute = AsyncMock(
        side_effect=[SandboxResult(exit_code=ec, stdout=out, stderr="") for ec, out in results]
    )
    return mgr


# ---------------------------------------------------------------------------
# detect_changed_files
# ---------------------------------------------------------------------------


async def test_detect_changed_files_returns_file_list() -> None:
    mgr = _mock_sandbox(
        (0, "packages/foo/src/foo.py\npackages/bar/src/bar.py\n"),
    )
    files = await detect_changed_files(mgr, "sb1", "/workspace/repo")
    assert files == ["packages/foo/src/foo.py", "packages/bar/src/bar.py"]


async def test_detect_changed_files_empty_output() -> None:
    mgr = _mock_sandbox((0, ""))
    files = await detect_changed_files(mgr, "sb1", "/workspace/repo")
    assert files == []


async def test_detect_changed_files_uses_base_branch() -> None:
    mgr = _mock_sandbox((0, "a.py\n"))
    await detect_changed_files(mgr, "sb1", "/workspace/repo", base_branch="develop")
    cmd = mgr.execute.call_args[0][1].command
    assert "origin/develop" in cmd
    assert "develop" in cmd


# ---------------------------------------------------------------------------
# select_affected_tests
# ---------------------------------------------------------------------------


async def test_select_affected_tests_maps_source_to_test() -> None:
    mgr = _mock_sandbox(
        # detect_changed_files
        (0, "src/lintel/domain/types.py\ntests/test_events.py\n"),
        # find command for source basename mapping
        (0, "packages/domain/tests/test_types.py\n"),
    )
    result = await select_affected_tests(mgr, "sb1", "/workspace/repo")
    assert isinstance(result, AffectedTestResult)
    # test_events.py is directly changed, test_types.py is inferred from types.py
    assert "tests/test_events.py" in result.test_files
    assert "packages/domain/tests/test_types.py" in result.test_files
    assert "src/lintel/domain/types.py" in result.source_files


async def test_select_affected_tests_no_changes() -> None:
    mgr = _mock_sandbox((0, ""))
    result = await select_affected_tests(mgr, "sb1", "/workspace/repo")
    assert result.changed_files == ()
    assert result.test_files == ()
    assert result.source_files == ()


async def test_select_affected_tests_only_test_files() -> None:
    mgr = _mock_sandbox(
        (0, "tests/test_foo.py\npackages/bar/tests/test_bar.py\n"),
    )
    result = await select_affected_tests(mgr, "sb1", "/workspace/repo")
    assert "tests/test_foo.py" in result.test_files
    assert "packages/bar/tests/test_bar.py" in result.test_files
    assert result.source_files == ()


async def test_select_affected_tests_ignores_init_files() -> None:
    mgr = _mock_sandbox(
        (0, "src/lintel/__init__.py\ntests/test_foo.py\n"),
    )
    result = await select_affected_tests(mgr, "sb1", "/workspace/repo")
    # __init__.py should not trigger source basename mapping
    assert result.test_files == ("tests/test_foo.py",)


# ---------------------------------------------------------------------------
# build_pytest_command
# ---------------------------------------------------------------------------


def test_build_pytest_command_with_files() -> None:
    cmd = build_pytest_command(("tests/test_a.py", "tests/test_b.py"))
    assert cmd is not None
    assert "pytest" in cmd
    assert "tests/test_a.py tests/test_b.py" in cmd
    assert "-v" in cmd


def test_build_pytest_command_empty() -> None:
    assert build_pytest_command(()) is None


# ---------------------------------------------------------------------------
# parse_test_results_per_module
# ---------------------------------------------------------------------------


def test_parse_results_from_summary_section() -> None:
    output = """
=========================== short test summary info ============================
FAILED tests/test_a.py::test_one - AssertionError
FAILED tests/test_a.py::test_two - AssertionError
FAILED tests/test_b.py::test_three - KeyError
========================= 3 failed, 10 passed in 1.5s =========================
"""
    results = parse_test_results_per_module(output)
    assert results["tests/test_a.py"] == "failed"
    assert results["tests/test_b.py"] == "failed"


def test_parse_results_all_passing() -> None:
    output = """
========================= 5 passed in 0.3s =========================
"""
    results = parse_test_results_per_module(output)
    assert results == {}


def test_parse_results_mixed() -> None:
    output = """
=========================== short test summary info ============================
FAILED tests/test_a.py::test_one - AssertionError
========================= 1 failed, 4 passed in 0.5s =========================
"""
    results = parse_test_results_per_module(output)
    assert results.get("tests/test_a.py") == "failed"
