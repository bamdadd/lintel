"""Chat API routes for direct conversation via API."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartConversationRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str
    project_id: str | None = None


class SendMessageRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str
    role: str = "user"


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class ChatStore:
    """Simple in-memory conversation store."""

    def __init__(self) -> None:
        self._conversations: dict[str, dict[str, Any]] = {}

    def create(
        self,
        *,
        conversation_id: str,
        user_id: str,
        display_name: str | None,
        project_id: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        conv: dict[str, Any] = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "display_name": display_name,
            "project_id": project_id,
            "created_at": now,
            "messages": [],
        }
        self._conversations[conversation_id] = conv
        return conv

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        return self._conversations.get(conversation_id)

    def delete(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None

    def list_all(
        self,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        results = list(self._conversations.values())
        if user_id is not None:
            results = [c for c in results if c["user_id"] == user_id]
        if project_id is not None:
            results = [
                c for c in results if c["project_id"] == project_id
            ]
        return results

    def add_message(
        self,
        conversation_id: str,
        *,
        user_id: str,
        display_name: str | None,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        conv = self._conversations.get(conversation_id)
        if conv is None:
            msg = f"Conversation {conversation_id} not found"
            raise KeyError(msg)
        message: dict[str, Any] = {
            "message_id": uuid4().hex,
            "user_id": user_id,
            "display_name": display_name,
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        conv["messages"].append(message)
        return message


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_chat_store(request: Request) -> ChatStore:
    return request.app.state.chat_store  # type: ignore[no-any-return]


ChatStoreDep = Annotated[ChatStore, Depends(get_chat_store)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/chat/conversations", status_code=201)
def create_conversation(
    body: StartConversationRequest,
    store: ChatStoreDep,
) -> dict[str, Any]:
    """Start a new conversation."""
    conversation_id = uuid4().hex
    conv = store.create(
        conversation_id=conversation_id,
        user_id=body.user_id,
        display_name=body.display_name,
        project_id=body.project_id,
    )
    store.add_message(
        conversation_id,
        user_id=body.user_id,
        display_name=body.display_name,
        role="user",
        content=body.message,
    )
    stub = (
        "[stub] Message received. "
        "AI processing not yet connected."
    )
    store.add_message(
        conversation_id,
        user_id="system",
        display_name="Lintel",
        role="agent",
        content=stub,
    )
    return conv


@router.get("/chat/conversations")
def list_conversations(
    store: ChatStoreDep,
    user_id: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List conversations with optional filters."""
    return store.list_all(user_id=user_id, project_id=project_id)


@router.get("/chat/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    store: ChatStoreDep,
) -> dict[str, Any]:
    """Get a conversation with its message history."""
    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
    return conv


@router.post(
    "/chat/conversations/{conversation_id}/messages",
    status_code=201,
)
def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    store: ChatStoreDep,
) -> dict[str, Any]:
    """Send a message to an existing conversation."""
    if body.role not in ("user", "agent", "system"):
        raise HTTPException(
            status_code=422,
            detail="role must be one of: user, agent, system",
        )
    try:
        return store.add_message(
            conversation_id,
            user_id=body.user_id,
            display_name=body.display_name,
            role=body.role,
            content=body.message,
        )
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )


@router.delete(
    "/chat/conversations/{conversation_id}",
    status_code=204,
)
def delete_conversation(
    conversation_id: str,
    store: ChatStoreDep,
) -> None:
    """Delete a conversation."""
    if not store.delete(conversation_id):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
