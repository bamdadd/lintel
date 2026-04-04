"""Tests for the RequestChangeFromSlack command."""

from __future__ import annotations

from lintel.contracts.types import ThreadRef
from lintel.slack.commands import RequestChangeFromSlack


def test_request_change_from_slack_creation() -> None:
    ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
    cmd = RequestChangeFromSlack(
        thread_ref=ref,
        feedback_text="Please rename the function to process_data",
        sender_id="U123",
        sender_name="alice",
        original_run_id="run-abc",
    )
    assert cmd.feedback_text == "Please rename the function to process_data"
    assert cmd.sender_id == "U123"
    assert cmd.original_run_id == "run-abc"
    assert cmd.thread_ref.workspace_id == "W1"


def test_request_change_from_slack_is_frozen() -> None:
    ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
    cmd = RequestChangeFromSlack(
        thread_ref=ref,
        feedback_text="Fix this",
        sender_id="U1",
        sender_name="bob",
    )
    try:
        cmd.feedback_text = "something else"  # type: ignore[misc]
        raise AssertionError("Should not be mutable")
    except AttributeError:
        pass
