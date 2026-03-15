"""In-memory chat conversation store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class ChatStore:
    """Simple in-memory conversation store.

    Uses ConversationData/ChatMessage models for construction but stores
    and returns plain dicts for backward compatibility with consumers.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, dict[str, Any]] = {}

    async def create(
        self,
        *,
        conversation_id: str,
        user_id: str,
        display_name: str | None,
        project_id: str | None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        from lintel.persistence.data_models import ConversationData

        conv = ConversationData(
            conversation_id=conversation_id,
            user_id=user_id,
            display_name=display_name,
            project_id=project_id,
            model_id=model_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        data = conv.model_dump()
        self._conversations[conversation_id] = data
        return data

    async def get(self, conversation_id: str) -> dict[str, Any] | None:
        return self._conversations.get(conversation_id)

    async def delete(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None

    async def list_all(
        self,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        results = list(self._conversations.values())
        if user_id is not None:
            results = [c for c in results if c["user_id"] == user_id]
        if project_id is not None:
            results = [c for c in results if c["project_id"] == project_id]
        return results

    async def update_fields(
        self,
        conversation_id: str,
        **fields: object,
    ) -> None:
        """Update arbitrary fields on a conversation."""
        conv = self._conversations.get(conversation_id)
        if conv is not None:
            conv.update(fields)

    async def add_message(
        self,
        conversation_id: str,
        *,
        user_id: str,
        display_name: str | None,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        from lintel.persistence.data_models import ChatMessage

        conv = self._conversations.get(conversation_id)
        if conv is None:
            msg = f"Conversation {conversation_id} not found"
            raise KeyError(msg)
        message = ChatMessage(
            message_id=uuid4().hex,
            user_id=user_id,
            display_name=display_name,
            role=role,
            content=content,
            timestamp=datetime.now(UTC).isoformat(),
        )
        data = message.model_dump()
        conv["messages"].append(data)
        return data
