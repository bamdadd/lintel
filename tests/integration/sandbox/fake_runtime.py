"""Fake AgentRuntime for sandbox integration tests.

Returns canned LLM responses per agent role, so we can test the full
stage pipeline without real LLM calls. The coder agent's response
includes tool_calls that write actual files into the sandbox.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.agents.types import AgentRole
    from lintel.models.types import ModelPolicy


# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

RESEARCH_REPORT = """\
## Relevant Files
- src/math_utils.py — Core math utility functions

## Current Architecture
Simple Python package with math utilities and a test suite.

## Key Patterns
- Pure functions, no side effects
- Tests mirror source structure under tests/

## Impact Analysis
- Adding new functions requires new tests in tests/test_math_utils.py

## Recommendations
- Add the new `subtract` function alongside existing `add` function
- Add corresponding tests
"""

PLAN_RESPONSE = json.dumps(
    {
        "tasks": [
            {
                "title": "Add subtract function to math_utils.py",
                "description": "Add a subtract(a, b) function to src/math_utils.py",
                "file_paths": ["src/math_utils.py"],
                "complexity": "S",
            },
            {
                "title": "Add divide function to math_utils.py",
                "description": "Add a divide(a, b) function with zero-division guard",
                "file_paths": ["src/math_utils.py"],
                "complexity": "S",
            },
            {
                "title": "Add tests for new functions",
                "description": "Add test_subtract and test_divide to tests/test_math_utils.py",
                "file_paths": ["tests/test_math_utils.py"],
                "complexity": "S",
            },
        ],
        "summary": "Add subtract and divide functions with tests",
    }
)

REVIEW_APPROVE = """\
## Code Review

### Correctness
The subtract and divide functions are implemented correctly.
The divide function properly handles zero division.

### Security
No security concerns — pure math functions with no I/O.

### Quality
Clean, consistent with existing code style.

### Tests
Both new functions have corresponding tests.

VERDICT: APPROVE
"""

_MATH_UTILS_CONTENT = """\
def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
"""

_TESTS_CONTENT = """\
import sys
sys.path.insert(0, "src")

from math_utils import add, subtract, divide, is_prime
import pytest


def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(1, 1) == 0


def test_divide():
    assert divide(10, 2) == 5.0
    assert divide(7, 2) == 3.5
    with pytest.raises(ValueError):
        divide(1, 0)


def test_is_prime():
    assert is_prime(2)
    assert is_prime(7)
    assert not is_prime(4)
    assert not is_prime(1)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_call(tool_name: str, arguments: dict[str, str]) -> dict[str, Any]:
    return {
        "id": f"call_{uuid4().hex[:8]}",
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(arguments),
        },
    }


def _generate_files_json(workspace_path: str) -> str:
    """Return JSON file output for the generate step."""
    return json.dumps(
        {
            "files": {
                "src/math_utils.py": _MATH_UTILS_CONTENT,
                "tests/test_math_utils.py": _TESTS_CONTENT,
            }
        }
    )


def _implement_tool_calls(workspace_path: str) -> list[dict[str, Any]]:
    return [
        _make_tool_call(
            "sandbox_write_file",
            {
                "path": f"{workspace_path}/src/math_utils.py",
                "content": _MATH_UTILS_CONTENT,
            },
        ),
        _make_tool_call(
            "sandbox_write_file",
            {
                "path": f"{workspace_path}/tests/test_math_utils.py",
                "content": _TESTS_CONTENT,
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tiny fakes
# ---------------------------------------------------------------------------


class FakeEventStore:
    """Swallows all events — no persistence needed for integration tests."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    async def append(self, stream_id: str, events: list[Any]) -> None:
        self.events.extend(events)

    async def read(
        self,
        stream_id: str,
        start: int = 0,
        limit: int = 100,
    ) -> list[Any]:
        return self.events


class FakeModelRouter:
    """Returns canned model responses keyed by agent role."""

    def __init__(self, workspace_path: str = "/workspace/repo") -> None:
        self._workspace_path = workspace_path
        self.last_stream_usage: dict[str, int] = {
            "input_tokens": 100,
            "output_tokens": 200,
        }

    async def select_model(
        self,
        agent_role: AgentRole,
        step_name: str,
    ) -> ModelPolicy:
        from lintel.models.types import ModelPolicy

        return ModelPolicy(provider="fake", model_name="fake-model")

    async def call_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        system_msg = _system_content(messages)
        has_tool_results = any(m.get("role") == "tool" for m in messages)

        # Generate step: return JSON file contents (no tools)
        if "respond only with a json" in system_msg.lower():
            return _text_response(_generate_files_json(self._workspace_path), 200, 100)

        # Fix step: return tool calls to fix code (has tools)
        if "fixing test failures" in system_msg.lower():
            if has_tool_results:
                return _text_response("Fix applied.")
            return {
                "content": None,
                "tool_calls": _implement_tool_calls(self._workspace_path),
                "usage": {"input_tokens": 200, "output_tokens": 100},
            }

        # Legacy: tool-based implement (for other workflows)
        if has_tool_results:
            return _text_response(
                "Implementation complete. Updated math_utils.py "
                "with subtract and divide functions, and added tests."
            )
        if "sandbox tools" in system_msg.lower() or "sandbox_write_file" in str(tools):
            return {
                "content": None,
                "tool_calls": _implement_tool_calls(self._workspace_path),
                "usage": {"input_tokens": 200, "output_tokens": 100},
            }

        if "code reviewer" in system_msg.lower():
            return _text_response(REVIEW_APPROVE, 150, 80)

        return _text_response("OK", 10, 5)

    async def stream_model(
        self,
        policy: ModelPolicy,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str]:
        system_msg = _system_content(messages)
        if "software planner" in system_msg.lower():
            content = PLAN_RESPONSE
        elif "software researcher" in system_msg.lower():
            content = RESEARCH_REPORT
        else:
            content = "OK"

        chunk_size = 50
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_fake_runtime(
    workspace_path: str = "/workspace/repo",
) -> AgentRuntime:  # noqa: F821
    """Create a fake AgentRuntime backed by FakeEventStore + FakeModelRouter."""
    from lintel.agents.runtime import AgentRuntime

    return AgentRuntime(
        event_store=FakeEventStore(),  # type: ignore[arg-type]
        model_router=FakeModelRouter(workspace_path),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _system_content(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return str(m.get("content", ""))
    return ""


def _text_response(
    text: str,
    input_tokens: int = 50,
    output_tokens: int = 30,
) -> dict[str, Any]:
    return {
        "content": text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


# ---------------------------------------------------------------------------
# Fake RepoProvider — records PR creation calls
# ---------------------------------------------------------------------------


class FakeRepoProvider:
    """Records create_pr / add_comment calls without hitting GitHub."""

    def __init__(self, pr_url: str = "https://github.com/test/repo/pull/42") -> None:
        self._pr_url = pr_url
        self.created_prs: list[dict[str, str]] = []
        self.comments: list[dict[str, Any]] = []

    async def create_pr(
        self,
        repo_url: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> str:
        self.created_prs.append(
            {
                "repo_url": repo_url,
                "head": head,
                "base": base,
                "title": title,
                "body": body,
            }
        )
        return self._pr_url

    async def add_comment(
        self,
        repo_url: str,
        pr_number: int,
        body: str,
    ) -> None:
        self.comments.append(
            {
                "repo_url": repo_url,
                "pr_number": pr_number,
                "body": body,
            }
        )
