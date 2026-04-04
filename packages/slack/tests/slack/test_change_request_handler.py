"""Tests for SlackChangeRequestHandler and is_change_request."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from lintel.slack.change_request_handler import (
    SlackChangeRequestHandler,
    is_change_request,
)

# ---------------------------------------------------------------------------
# is_change_request detection tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Please update the variable name to camelCase",
        "Can you fix the import order?",
        "Change the button colour to blue",
        "Actually, I want this to use async instead",
        "The function should be named 'process_data'",
        "Remove the unused import on line 12",
        "Replace the for loop with a list comprehension",
        "Move the helper to the utils module",
        "This needs to handle the edge case where input is empty",
        "Rename the class to UserService",
    ],
)
def test_is_change_request_positive(text: str) -> None:
    assert is_change_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ok",
        "thanks",
        "LGTM",
        "hi",
        "  ",
        "yes",
    ],
)
def test_is_change_request_negative(text: str) -> None:
    assert is_change_request(text) is False


# ---------------------------------------------------------------------------
# SlackChangeRequestHandler tests
# ---------------------------------------------------------------------------


@dataclass
class FakePipelineRun:
    run_id: str = "run-123"
    project_id: str = "proj-1"
    work_item_id: str = "wi-1"
    workflow_definition_id: str = "feature_to_pr"
    trigger_type: str = "chat:conv-abc"
    status: str = "succeeded"
    stages: tuple[Any, ...] = ()


@dataclass
class FakeThreadRef:
    workspace_id: str = "W1"
    channel_id: str = "C1"
    thread_ts: str = "conv-abc"


class FakePipelineStore:
    def __init__(self, runs: list[Any] | None = None) -> None:
        self._runs = runs or []

    async def list_all(self) -> list[Any]:
        return self._runs

    async def get(self, run_id: str) -> FakePipelineRun | None:
        for r in self._runs:
            if r.run_id == run_id:
                return r
        return None


class FakeWorkItemStore:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None) -> None:
        self._items = items or {}

    async def get(self, item_id: str) -> dict[str, Any] | None:
        return self._items.get(item_id)


async def test_find_completed_run_for_thread() -> None:
    run = FakePipelineRun()
    handler = SlackChangeRequestHandler(
        pipeline_store=FakePipelineStore([run]),
        work_item_store=FakeWorkItemStore(),
    )
    ref = FakeThreadRef()
    result = await handler.find_completed_run_for_thread(ref)
    assert result is not None
    assert result.run_id == "run-123"


async def test_find_completed_run_no_match() -> None:
    run = FakePipelineRun(trigger_type="chat:other-conv")
    handler = SlackChangeRequestHandler(
        pipeline_store=FakePipelineStore([run]),
        work_item_store=FakeWorkItemStore(),
    )
    ref = FakeThreadRef()
    result = await handler.find_completed_run_for_thread(ref)
    assert result is None


async def test_find_completed_run_only_matches_terminal_status() -> None:
    run = FakePipelineRun(status="running")
    handler = SlackChangeRequestHandler(
        pipeline_store=FakePipelineStore([run]),
        work_item_store=FakeWorkItemStore(),
    )
    ref = FakeThreadRef()
    result = await handler.find_completed_run_for_thread(ref)
    assert result is None


async def test_extract_change_context() -> None:
    run = FakePipelineRun()
    handler = SlackChangeRequestHandler(
        pipeline_store=FakePipelineStore([run]),
        work_item_store=FakeWorkItemStore(
            {
                "wi-1": {
                    "branch_name": "lintel/feat/abc123",
                    "pr_url": "https://github.com/org/repo/pull/42",
                },
            }
        ),
    )
    ctx = await handler.extract_change_context(run)
    assert ctx["original_run_id"] == "run-123"
    assert ctx["project_id"] == "proj-1"
    assert ctx["work_item_id"] == "wi-1"
    assert ctx["feature_branch"] == "lintel/feat/abc123"
    assert ctx["pr_url"] == "https://github.com/org/repo/pull/42"


async def test_extract_change_context_no_work_item() -> None:
    run = FakePipelineRun(work_item_id="")
    handler = SlackChangeRequestHandler(
        pipeline_store=FakePipelineStore([run]),
        work_item_store=FakeWorkItemStore(),
    )
    ctx = await handler.extract_change_context(run)
    assert ctx["feature_branch"] == ""
    assert ctx["pr_url"] == ""
