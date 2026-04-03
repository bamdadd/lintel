"""Tests for implementation retry on test failure with error feedback."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from lintel.contracts.types import ThreadRef
from lintel.sandbox.types import SandboxJob, SandboxResult, SandboxStatus

if TYPE_CHECKING:
    from lintel.sandbox.types import SandboxConfig

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSandboxManager:
    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {"sb-1": {}}
        self.written_files: list[str] = []

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        return "sb-1"

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        self.written_files.append(path)

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        return SandboxStatus.RUNNING

    async def collect_artifacts(
        self, sandbox_id: str, workdir: str = "/workspace"
    ) -> dict[str, str]:
        return {"type": "diff", "content": "diff"}

    async def destroy(self, sandbox_id: str) -> None:
        pass

    async def reconnect_network(self, sandbox_id: str) -> None:
        pass

    async def disconnect_network(self, sandbox_id: str) -> None:
        pass


class _FakeModelPolicy:
    provider = "litellm"
    model_name = "gpt-4"


class _FakeModelRouter:
    async def select_model(self, role: object, step: str) -> _FakeModelPolicy:
        return _FakeModelPolicy()


class _FakeRuntime:
    def __init__(self) -> None:
        self._model_router = _FakeModelRouter()
        self.call_count = 0
        self.prompts: list[str] = []

    async def execute_step(self, **kwargs: object) -> dict[str, object]:
        self.call_count += 1
        messages: list[dict[str, str]] = kwargs.get("messages", [])  # type: ignore[assignment]
        for m in messages:
            if m.get("role") == "user":
                self.prompts.append(m["content"])
        step = kwargs.get("step_name", "")
        if step == "implement_generate":
            return {
                "content": '{"files": {"src/foo.py": "print(1)"}}',
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }
        return {"content": "fixed", "usage": {"input_tokens": 5, "output_tokens": 5}}


def _make_state() -> dict[str, object]:
    return {
        "thread_ref": "ws:ch:ts",
        "correlation_id": str(uuid4()),
        "current_phase": "implementing",
        "sanitized_messages": ["add feature"],
        "intent": "feature",
        "plan": {"tasks": ["do thing"], "summary": "Do the thing"},
        "agent_outputs": [],
        "pending_approvals": [],
        "sandbox_id": "sb-1",
        "sandbox_results": [],
        "pr_url": "",
        "error": None,
        "run_id": "",
    }


def _thread_ref() -> ThreadRef:
    return ThreadRef(workspace_id="ws", channel_id="ch", thread_ts="ts")


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------

_DISC_MOD = "lintel.workflows.nodes._impl_discovery"


def _mock_run_tests(exit_codes: list[int]) -> AsyncMock:
    """Return a mock run_tests that yields exit codes in order."""
    idx = {"i": 0}

    async def _run_tests(*args: object, **kwargs: object) -> tuple[str, int]:
        i = min(idx["i"], len(exit_codes) - 1)
        idx["i"] += 1
        ec = exit_codes[i]
        out = "OK" if ec == 0 else "FAILED tests/test_x.py::test_a - AssertionError"
        return out, ec

    return AsyncMock(side_effect=_run_tests)


def _mock_fix_failures() -> AsyncMock:
    async def _fix(*args: object, **kwargs: object) -> dict[str, object]:
        return {"content": "fixed", "usage": {"input_tokens": 5, "output_tokens": 5}}

    return AsyncMock(side_effect=_fix)


def _mock_run_lint_pass() -> AsyncMock:
    return AsyncMock(return_value=("", 0))


# ---------------------------------------------------------------------------
# Structured path tests
# ---------------------------------------------------------------------------


class TestStructuredImplRetry:
    async def test_passes_first_try_no_retry(self) -> None:
        from lintel.workflows.nodes._impl_structured import implement_structured

        runtime = _FakeRuntime()
        with (
            patch(f"{_DISC_MOD}.run_tests", _mock_run_tests([0])),
            patch(f"{_DISC_MOD}.run_lint", _mock_run_lint_pass()),
            patch(f"{_DISC_MOD}.fix_failures", _mock_fix_failures()),
        ):
            _output, passed, _usage = await implement_structured(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is True
        gen_prompts = [p for p in runtime.prompts if "Previous Attempt Failed" not in p]
        assert len(gen_prompts) == 1

    async def test_retries_with_error_feedback_on_failure(self) -> None:
        from lintel.workflows.nodes._impl_structured import (
            MAX_FIX_ATTEMPTS,
            implement_structured,
        )

        exits = [1] * (MAX_FIX_ATTEMPTS + 1) + [0]
        runtime = _FakeRuntime()

        with (
            patch(f"{_DISC_MOD}.run_tests", _mock_run_tests(exits)),
            patch(f"{_DISC_MOD}.run_lint", _mock_run_lint_pass()),
            patch(f"{_DISC_MOD}.fix_failures", _mock_fix_failures()),
        ):
            _output, passed, _usage = await implement_structured(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is True
        retry_prompts = [p for p in runtime.prompts if "Previous Attempt Failed" in p]
        assert len(retry_prompts) >= 1

    async def test_gives_up_after_max_retries(self) -> None:
        from lintel.workflows.nodes._impl_structured import (
            MAX_FIX_ATTEMPTS,
            MAX_IMPL_RETRIES,
            implement_structured,
        )

        total = (MAX_IMPL_RETRIES + 1) * (MAX_FIX_ATTEMPTS + 1)
        runtime = _FakeRuntime()

        with (
            patch(f"{_DISC_MOD}.run_tests", _mock_run_tests([1] * total)),
            patch(f"{_DISC_MOD}.run_lint", _mock_run_lint_pass()),
            patch(f"{_DISC_MOD}.fix_failures", _mock_fix_failures()),
        ):
            output, passed, _usage = await implement_structured(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is False
        assert "failing" in output.lower()


# ---------------------------------------------------------------------------
# TDD path tests
# ---------------------------------------------------------------------------


def _tdd_patches(exit_codes: list[int]):  # noqa: ANN202
    """Context manager stack for TDD-specific mocks."""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch(f"{_DISC_MOD}.run_tests", _mock_run_tests(exit_codes)))
    stack.enter_context(patch(f"{_DISC_MOD}.run_lint", _mock_run_lint_pass()))
    stack.enter_context(patch(f"{_DISC_MOD}.auto_format", AsyncMock()))
    stack.enter_context(
        patch(
            f"{_DISC_MOD}.discover_dev_commands",
            AsyncMock(return_value=("make test", "make lint", "make typecheck", "pytest <f>")),
        )
    )
    stack.enter_context(
        patch(f"{_DISC_MOD}.load_skill_system_prompt", AsyncMock(return_value="system"))
    )
    stack.enter_context(
        patch(
            "lintel.domain.skills.discover_test_command.discover_test_command",
            AsyncMock(return_value={"test_command": "make test", "setup_commands": []}),
        )
    )
    return stack


class TestTddImplRetry:
    async def test_passes_first_try_no_retry(self) -> None:
        from lintel.workflows.nodes._impl_tdd import implement_tdd

        runtime = _FakeRuntime()

        with _tdd_patches([0]):
            _output, passed, _usage = await implement_tdd(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is True

    async def test_retries_tdd_session_with_error_feedback(self) -> None:
        from lintel.workflows.nodes._impl_tdd import (
            MAX_TDD_FIX_ATTEMPTS,
            implement_tdd,
        )

        exits = [1] * (MAX_TDD_FIX_ATTEMPTS + 1) + [0]
        runtime = _FakeRuntime()

        with _tdd_patches(exits):
            _output, passed, _usage = await implement_tdd(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is True
        retry_prompts = [p for p in runtime.prompts if "Previous Attempt Failed" in p]
        assert len(retry_prompts) >= 1

    async def test_gives_up_after_max_tdd_retries(self) -> None:
        from lintel.workflows.nodes._impl_tdd import (
            MAX_TDD_FIX_ATTEMPTS,
            MAX_TDD_IMPL_RETRIES,
            implement_tdd,
        )

        total = (MAX_TDD_IMPL_RETRIES + 1) * (MAX_TDD_FIX_ATTEMPTS + 1)
        runtime = _FakeRuntime()

        with _tdd_patches([1] * total):
            _output, passed, _usage = await implement_tdd(
                agent_runtime=runtime,  # type: ignore[arg-type]
                thread_ref=_thread_ref(),
                sandbox_manager=_FakeSandboxManager(),  # type: ignore[arg-type]
                sandbox_id="sb-1",
                workspace_path="/workspace/repo",
                user_prompt="do the thing",
                config={"configurable": {}},
                state=_make_state(),  # type: ignore[arg-type]
            )

        assert passed is False
