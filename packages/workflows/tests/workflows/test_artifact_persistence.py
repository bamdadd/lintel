"""Tests for artifact and test result persistence in workflow nodes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from lintel.contracts.types import SandboxResult


def _make_state(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_ref": "W1:C1:ts1",
        "correlation_id": "run-1",
        "sanitized_messages": ["add feature"],
        "run_id": "run-1",
        "sandbox_id": "sbx-1",
        "workspace_path": "/workspace/repo",
        "work_item_id": "wi-1",
        "plan": {"summary": "Do it", "tasks": [{"title": "task1"}]},
        "repo_branch": "main",
    }
    base.update(overrides)
    return base


async def test_implement_persists_code_artifact() -> None:
    """REQ-2.5: implement node stores diff as CodeArtifact."""
    from lintel.workflows.nodes.implement import spawn_implementation

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=SandboxResult(exit_code=0, stdout="", stderr=""))
    sandbox.collect_artifacts = AsyncMock(return_value={"content": "+new line\n-old line"})

    artifact_store = AsyncMock()
    added_artifacts: list[Any] = []
    artifact_store.add = AsyncMock(side_effect=lambda a: added_artifacts.append(a))

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "agent_runtime": None,
            "code_artifact_store": artifact_store,
            "pipeline_store": None,
        }
    }

    result = await spawn_implementation(_make_state(), config)
    assert result.get("current_phase") is not None

    # Should have persisted one code artifact
    assert len(added_artifacts) == 1
    artifact = added_artifacts[0]
    assert artifact.artifact_type == "diff"
    assert "+new line" in artifact.content
    assert artifact.run_id == "run-1"
    assert artifact.work_item_id == "wi-1"


async def test_implement_no_artifact_when_no_diff() -> None:
    """No artifact stored when diff is empty."""
    from lintel.workflows.nodes.implement import spawn_implementation

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(return_value=SandboxResult(exit_code=0, stdout="", stderr=""))
    sandbox.collect_artifacts = AsyncMock(return_value={"content": ""})

    artifact_store = AsyncMock()

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "agent_runtime": None,
            "code_artifact_store": artifact_store,
            "pipeline_store": None,
        }
    }

    await spawn_implementation(_make_state(), config)
    artifact_store.add.assert_not_called()


async def test_test_node_persists_test_result() -> None:
    """REQ-2.5: test node stores result as TestResult."""
    from unittest.mock import patch

    from lintel.workflows.nodes.test_code import run_tests

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=0, stdout="3 passed", stderr=""),
    )

    result_store = AsyncMock()
    added_results: list[Any] = []
    result_store.add = AsyncMock(side_effect=lambda r: added_results.append(r))

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "test_result_store": result_store,
            "pipeline_store": None,
        }
    }

    discovery = {"test_command": "make test", "setup_commands": []}
    with patch(
        "lintel.domain.skills.discover_test_command.discover_test_command",
        new_callable=AsyncMock,
        return_value=discovery,
    ):
        result = await run_tests(_make_state(), config)
    assert result["agent_outputs"][0]["verdict"] == "passed"

    assert len(added_results) == 1
    test_result = added_results[0]
    assert test_result.verdict.value == "passed"
    assert test_result.run_id == "run-1"


async def test_test_node_records_failure() -> None:
    """Failed tests are stored with FAILED verdict."""
    from unittest.mock import patch

    from lintel.workflows.nodes.test_code import run_tests

    sandbox = AsyncMock()
    sandbox.execute = AsyncMock(
        return_value=SandboxResult(exit_code=1, stdout="", stderr="FAILED test_foo"),
    )

    result_store = AsyncMock()
    added_results: list[Any] = []
    result_store.add = AsyncMock(side_effect=lambda r: added_results.append(r))

    config: dict[str, Any] = {
        "configurable": {
            "sandbox_manager": sandbox,
            "test_result_store": result_store,
            "pipeline_store": None,
        }
    }

    discovery = {"test_command": "make test", "setup_commands": []}
    with patch(
        "lintel.domain.skills.discover_test_command.discover_test_command",
        new_callable=AsyncMock,
        return_value=discovery,
    ):
        result = await run_tests(_make_state(), config)
    assert result["agent_outputs"][0]["verdict"] == "failed"

    assert len(added_results) == 1
    assert added_results[0].verdict.value == "failed"
    assert len(added_results[0].failures) > 0
