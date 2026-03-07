"""Tests for the implement workflow node."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from lintel.contracts.errors import SandboxNotFoundError
from lintel.contracts.types import (
    SandboxConfig,
    SandboxJob,
    SandboxResult,
    SandboxStatus,
    ThreadRef,
)
from lintel.workflows.nodes.implement import spawn_implementation


class DummySandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}
        self.created: list[str] = []
        self.destroyed: list[str] = []

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        self.created.append(sandbox_id)
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        pass

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        return SandboxStatus.RUNNING

    async def collect_artifacts(self, sandbox_id: str) -> dict[str, Any]:
        return {"type": "diff", "content": "some diff"}

    async def destroy(self, sandbox_id: str) -> None:
        self.destroyed.append(sandbox_id)
        self._sandboxes.pop(sandbox_id, None)


def _make_state(sandbox_id: str = "sandbox-123") -> dict[str, Any]:
    return {
        "thread_ref": "thread:W1:C1:1.0",
        "correlation_id": str(uuid4()),
        "current_phase": "implementing",
        "sanitized_messages": ["add a button"],
        "intent": "feature",
        "plan": {"tasks": ["add button component"], "summary": "Add a button"},
        "agent_outputs": [],
        "pending_approvals": [],
        "sandbox_id": sandbox_id,
        "sandbox_results": [],
        "pr_url": "",
        "error": None,
    }


class TestSpawnImplementation:
    async def test_returns_error_when_no_sandbox(self) -> None:
        manager = DummySandboxManager()
        state = _make_state(sandbox_id=None)  # type: ignore[arg-type]

        result = await spawn_implementation(state, {"configurable": {"sandbox_manager": manager}})

        assert result["error"] is not None
        assert result["current_phase"] == "closed"

    async def test_returns_artifacts_with_sandbox(self) -> None:
        manager = DummySandboxManager()
        # Pre-create a sandbox so it exists in the manager
        sandbox_id = "test-sandbox-1"
        manager._sandboxes[sandbox_id] = {}
        state = _make_state(sandbox_id=sandbox_id)

        result = await spawn_implementation(state, {"configurable": {"sandbox_manager": manager}})

        assert result["current_phase"] == "testing"
        assert len(result["sandbox_results"]) == 1
        assert result["sandbox_results"][0]["type"] == "diff"
        assert len(result["agent_outputs"]) == 1

    async def test_collects_artifacts_without_agent_runtime(self) -> None:
        manager = DummySandboxManager()
        sandbox_id = "test-sandbox-2"
        manager._sandboxes[sandbox_id] = {}
        state = _make_state(sandbox_id=sandbox_id)

        result = await spawn_implementation(state, {"configurable": {"sandbox_manager": manager, "agent_runtime": None}})

        assert "No agent runtime" in result["agent_outputs"][0]["output"]
