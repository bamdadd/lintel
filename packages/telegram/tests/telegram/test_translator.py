"""Tests for Telegram event translator."""

from __future__ import annotations

from lintel.contracts.channel_type import ChannelType
from lintel.telegram.translator import translate_callback_query, translate_message_update


class TestTranslateMessageUpdate:
    def test_translates_private_message(self) -> None:
        update = {
            "message": {
                "message_id": 42,
                "from": {"id": 12345, "first_name": "Alice"},
                "chat": {"id": 67890, "type": "private"},
                "text": "Hello bot",
            }
        }
        result = translate_message_update(update)
        assert result is not None
        assert result.channel_type == ChannelType.TELEGRAM
        assert result.channel_id == "67890"
        assert result.thread_id == "67890"  # private: chat_id as thread_id
        assert result.sender_id == "12345"
        assert result.text == "Hello bot"

    def test_translates_group_mention(self) -> None:
        update = {
            "message": {
                "message_id": 100,
                "from": {"id": 12345},
                "chat": {"id": -100123, "type": "supergroup"},
                "text": "@testbot do something",
            }
        }
        result = translate_message_update(update, bot_username="testbot")
        assert result is not None
        assert result.text == "do something"
        assert result.channel_id == "-100123"

    def test_ignores_group_without_mention(self) -> None:
        update = {
            "message": {
                "message_id": 100,
                "from": {"id": 12345},
                "chat": {"id": -100123, "type": "group"},
                "text": "hello everyone",
            }
        }
        result = translate_message_update(update, bot_username="testbot")
        assert result is None

    def test_forum_topic_message(self) -> None:
        update = {
            "message": {
                "message_id": 200,
                "message_thread_id": 5,
                "from": {"id": 12345},
                "chat": {"id": -100456, "type": "supergroup"},
                "text": "@mybot help me",
            }
        }
        result = translate_message_update(update, bot_username="mybot")
        assert result is not None
        assert result.thread_id == "5"

    def test_returns_none_for_no_message(self) -> None:
        assert translate_message_update({}) is None

    def test_returns_none_for_empty_text(self) -> None:
        update = {
            "message": {
                "message_id": 1,
                "from": {"id": 1},
                "chat": {"id": 1, "type": "private"},
                "text": "",
            }
        }
        assert translate_message_update(update) is None

    def test_processes_group_when_no_bot_username(self) -> None:
        update = {
            "message": {
                "message_id": 100,
                "from": {"id": 12345},
                "chat": {"id": -100123, "type": "group"},
                "text": "hello everyone",
            }
        }
        result = translate_message_update(update, bot_username="")
        assert result is not None


class TestTranslateCallbackQuery:
    def test_extracts_callback_data(self) -> None:
        update = {
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 12345},
                "data": "a:req-123",
            }
        }
        result = translate_callback_query(update)
        assert result is not None
        data, query = result
        assert data == "a:req-123"
        assert query["id"] == "cb-1"

    def test_returns_none_without_callback(self) -> None:
        assert translate_callback_query({"message": {}}) is None

    def test_returns_none_for_empty_data(self) -> None:
        update = {"callback_query": {"id": "cb-1", "data": ""}}
        assert translate_callback_query(update) is None
