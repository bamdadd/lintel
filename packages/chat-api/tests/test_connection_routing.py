"""Tests for connection-scoped message routing and workflow filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lintel.channel_connections_api.types import ChannelConnection
from lintel.chat_api.service import ChatService
from lintel.contracts.channel_type import ChannelType
from lintel.contracts.inbound_message import InboundMessage

# --- InboundMessage connection_id tests ---


class TestInboundMessageConnectionId:
    def test_default_connection_id_is_empty(self) -> None:
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="t1",
            sender_id="U1",
            text="hello",
        )
        assert msg.connection_id == ""

    def test_connection_id_set(self) -> None:
        msg = InboundMessage(
            channel_type=ChannelType.SLACK,
            channel_id="C123",
            thread_id="t1",
            sender_id="U1",
            text="hello",
            connection_id="conn-abc",
        )
        assert msg.connection_id == "conn-abc"


# --- ChatService.check_workflow_allowed tests ---


class TestCheckWorkflowAllowed:
    def _make_svc(self) -> ChatService:
        request = MagicMock()
        store = AsyncMock()
        return ChatService(request, store)

    def test_no_connection_allows_all(self) -> None:
        svc = self._make_svc()
        assert svc.check_workflow_allowed(None, "feature_to_pr") is None

    def test_empty_allowed_workflows_allows_all(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1",
            provider="slack",
            channel_id="C123",
            workspace_id="T123",
            allowed_workflows=(),
        )
        assert svc.check_workflow_allowed(conn, "feature_to_pr") is None

    def test_workflow_in_allowed_list(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1",
            provider="slack",
            channel_id="C123",
            workspace_id="T123",
            allowed_workflows=("feature_to_pr", "bug_fix"),
        )
        assert svc.check_workflow_allowed(conn, "feature_to_pr") is None

    def test_workflow_not_in_allowed_list(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1",
            provider="slack",
            channel_id="C123",
            workspace_id="T123",
            allowed_workflows=("bug_fix",),
        )
        result = svc.check_workflow_allowed(conn, "feature_to_pr")
        assert result is not None
        assert "not configured for feature_to_pr" in result


# --- ChatService.check_project_allowed tests ---


class TestCheckProjectAllowed:
    def _make_svc(self) -> ChatService:
        request = MagicMock()
        store = AsyncMock()
        return ChatService(request, store)

    def test_no_connection_allows_all(self) -> None:
        svc = self._make_svc()
        assert svc.check_project_allowed(None, "proj-1") is None

    def test_empty_project_ids_allows_all(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1", provider="slack", channel_id="C123", workspace_id="T123", project_ids=()
        )
        assert svc.check_project_allowed(conn, "proj-1") is None

    def test_project_in_allowed_list(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1",
            provider="slack",
            channel_id="C123",
            workspace_id="T123",
            project_ids=("proj-1", "proj-2"),
        )
        assert svc.check_project_allowed(conn, "proj-1") is None

    def test_project_not_in_allowed_list(self) -> None:
        svc = self._make_svc()
        conn = ChannelConnection(
            id="conn-1",
            provider="slack",
            channel_id="C123",
            workspace_id="T123",
            project_ids=("proj-1",),
        )
        result = svc.check_project_allowed(conn, "proj-other")
        assert result is not None
        assert "not configured for project proj-other" in result


# --- Slack translator connection_id pass-through ---


class TestSlackTranslatorConnectionId:
    def test_connection_id_forwarded(self) -> None:
        from lintel.slack.event_translator import translate_message_event

        event = {
            "type": "message",
            "text": "hello",
            "user": "U12345",
            "channel": "C99999",
            "team": "T11111",
            "ts": "1234567890.123456",
            "thread_ts": "1234567890.000000",
        }
        result = translate_message_event(event, connection_id="conn-slack-1")
        assert result is not None
        assert result.connection_id == "conn-slack-1"

    def test_connection_id_defaults_empty(self) -> None:
        from lintel.slack.event_translator import translate_message_event

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
        assert result.connection_id == ""


# --- Telegram translator connection_id pass-through ---


class TestTelegramTranslatorConnectionId:
    def test_connection_id_forwarded(self) -> None:
        from lintel.telegram.translator import translate_message_update

        update = {
            "message": {
                "message_id": 42,
                "from": {"id": 12345, "first_name": "Alice"},
                "chat": {"id": 67890, "type": "private"},
                "text": "Hello bot",
            }
        }
        result = translate_message_update(update, connection_id="conn-tg-1")
        assert result is not None
        assert result.connection_id == "conn-tg-1"

    def test_connection_id_defaults_empty(self) -> None:
        from lintel.telegram.translator import translate_message_update

        update = {
            "message": {
                "message_id": 42,
                "from": {"id": 12345},
                "chat": {"id": 67890, "type": "private"},
                "text": "Hello",
            }
        }
        result = translate_message_update(update)
        assert result is not None
        assert result.connection_id == ""


# --- ChannelConnection type tests ---


class TestChannelConnectionFields:
    def test_allowed_workflows_default_empty(self) -> None:
        from lintel.channel_connections_api.types import ChannelConnection

        conn = ChannelConnection(
            id="c1",
            provider="slack",
            channel_id="C1",
            workspace_id="T1",
        )
        assert conn.allowed_workflows == ()
        assert conn.project_ids == ()

    def test_allowed_workflows_set(self) -> None:
        from lintel.channel_connections_api.types import ChannelConnection

        conn = ChannelConnection(
            id="c1",
            provider="slack",
            channel_id="C1",
            workspace_id="T1",
            allowed_workflows=("feature_to_pr", "bug_fix"),
            project_ids=("proj-1",),
        )
        assert conn.allowed_workflows == ("feature_to_pr", "bug_fix")
        assert conn.project_ids == ("proj-1",)
