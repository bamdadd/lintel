"""Tests for Slack event translator."""

from __future__ import annotations

from lintel.contracts.commands import GrantApproval, ProcessIncomingMessage, RejectApproval
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.channels.slack.event_translator import (
    translate_approval_action,
    translate_message_event,
)


class TestTranslateMessageEvent:
    def test_translates_valid_message(self) -> None:
        event = {
            "type": "message",
            "text": "implement user auth",
            "user": "U12345",
            "channel": "C99999",
            "team": "T11111",
            "ts": "1234567890.123456",
            "thread_ts": "1234567890.000000",
        }
        result = translate_message_event(event)
        assert result is not None
        assert isinstance(result, ProcessIncomingMessage)
        assert result.thread_ref == ThreadRef(
            workspace_id="T11111",
            channel_id="C99999",
            thread_ts="1234567890.000000",
        )
        assert result.raw_text == "implement user auth"
        assert result.sender_id == "U12345"

    def test_uses_ts_as_thread_ts_when_not_in_thread(self) -> None:
        event = {
            "type": "message",
            "text": "hello",
            "user": "U12345",
            "channel": "C99999",
            "team": "T11111",
            "ts": "1234567890.123456",
        }
        result = translate_message_event(event)
        assert result is not None
        assert result.thread_ref.thread_ts == "1234567890.123456"

    def test_ignores_bot_messages(self) -> None:
        event = {
            "type": "message",
            "text": "bot reply",
            "bot_id": "B12345",
            "channel": "C99999",
            "team": "T11111",
            "ts": "1234567890.123456",
        }
        assert translate_message_event(event) is None

    def test_ignores_subtype_messages(self) -> None:
        event = {
            "type": "message",
            "subtype": "channel_join",
            "text": "joined",
            "user": "U12345",
            "channel": "C99999",
            "team": "T11111",
            "ts": "1234567890.123456",
        }
        assert translate_message_event(event) is None

    def test_returns_none_for_missing_required_fields(self) -> None:
        event = {"type": "message", "text": "hello"}
        assert translate_message_event(event) is None

    def test_returns_none_for_empty_channel(self) -> None:
        event = {
            "type": "message",
            "text": "hello",
            "user": "U12345",
            "channel": "",
            "team": "T11111",
            "ts": "1234567890.123456",
        }
        assert translate_message_event(event) is None


class TestTranslateApprovalAction:
    def test_translates_approve_action(self) -> None:
        body = {
            "actions": [
                {
                    "action_id": "approve:spec_approval:thread:T11111:C99999:1234567890.000000",
                }
            ],
            "user": {"id": "U12345", "name": "alice"},
        }
        result = translate_approval_action(body)
        assert isinstance(result, GrantApproval)
        assert result.thread_ref == ThreadRef(
            workspace_id="T11111",
            channel_id="C99999",
            thread_ts="1234567890.000000",
        )
        assert result.gate_type == "spec_approval"
        assert result.approver_id == "U12345"
        assert result.approver_name == "alice"

    def test_translates_reject_action(self) -> None:
        body = {
            "actions": [
                {
                    "action_id": "reject:merge_approval:thread:T11111:C99999:1234567890.000000",
                    "value": "needs changes",
                }
            ],
            "user": {"id": "U12345", "name": "bob"},
        }
        result = translate_approval_action(body)
        assert isinstance(result, RejectApproval)
        assert result.gate_type == "merge_approval"
        assert result.rejector_id == "U12345"
        assert result.reason == "needs changes"

    def test_returns_none_for_empty_actions(self) -> None:
        assert translate_approval_action({"actions": []}) is None

    def test_returns_none_for_missing_actions(self) -> None:
        assert translate_approval_action({}) is None

    def test_returns_none_for_malformed_action_id(self) -> None:
        body = {
            "actions": [{"action_id": "bad_format"}],
            "user": {"id": "U12345", "name": "alice"},
        }
        assert translate_approval_action(body) is None

    def test_returns_none_for_malformed_thread_ref(self) -> None:
        body = {
            "actions": [{"action_id": "approve:spec:bad_ref"}],
            "user": {"id": "U12345", "name": "alice"},
        }
        assert translate_approval_action(body) is None
