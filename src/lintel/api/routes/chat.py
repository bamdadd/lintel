"""Chat API routes for direct conversation via API."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import ModelPolicy, ThreadRef

logger = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartConversationRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str | None = None
    project_id: str | None = None
    model_id: str | None = None


class SendMessageRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str
    role: str = "user"
    model_id: str | None = None


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class ChatStore:
    """Simple in-memory conversation store."""

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
        now = datetime.now(UTC).isoformat()
        conv: dict[str, Any] = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "display_name": display_name,
            "project_id": project_id,
            "model_id": model_id,
            "created_at": now,
            "messages": [],
        }
        self._conversations[conversation_id] = conv
        return conv

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

    async def add_message(
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
# Model resolution
# ---------------------------------------------------------------------------


async def _resolve_model(
    request: Request,
    model_id: str | None,
) -> tuple[ModelPolicy | None, str | None]:
    """Resolve a model_id to a ModelPolicy and api_base.

    Falls back to the default model if no model_id is given.
    Returns (None, None) if no model can be resolved.
    """
    if model_id is None:
        # Try to find a default model
        model_store = getattr(request.app.state, "model_store", None)
        if model_store is None:
            return None, None
        models = await model_store.list_all()
        default_models = [m for m in models if m.is_default]
        if not default_models:
            return None, None
        model = default_models[0]
        model_id = model.model_id
    else:
        model_store = getattr(request.app.state, "model_store", None)
        if model_store is None:
            return None, None
        model = await model_store.get(model_id)
        if model is None:
            return None, None

    provider_store = getattr(request.app.state, "ai_provider_store", None)
    if provider_store is None:
        return None, None
    provider = await provider_store.get(model.provider_id)
    if provider is None:
        return None, None

    policy = ModelPolicy(
        provider=provider.provider_type.value,
        model_name=model.model_name,
        max_tokens=model.max_tokens,
        temperature=model.temperature,
        extra_params=model.config,
    )
    api_base = provider.api_base or None
    return policy, api_base


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _thread_ref_from_conversation(conversation_id: str) -> ThreadRef:
    """Map a chat conversation to a ThreadRef for workflow dispatch."""
    return ThreadRef(
        workspace_id="lintel-chat",
        channel_id="chat",
        thread_ts=conversation_id,
    )


@router.post("/chat/conversations", status_code=201)
async def create_conversation(
    body: StartConversationRequest,
    store: ChatStoreDep,
    request: Request,
) -> dict[str, Any]:
    """Start a new conversation, optionally with an initial message."""
    conversation_id = uuid4().hex
    conv = await store.create(
        conversation_id=conversation_id,
        user_id=body.user_id,
        display_name=body.display_name,
        project_id=body.project_id,
        model_id=body.model_id,
    )

    # If no message, just create the empty conversation
    if not body.message:
        return conv

    await store.add_message(
        conversation_id,
        user_id=body.user_id,
        display_name=body.display_name,
        role="user",
        content=body.message,
    )

    chat_router = getattr(request.app.state, "chat_router", None)
    if chat_router is None:
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content="[stub] Message received. AI processing not yet connected.",
        )
        return conv

    model_policy, api_base = await _resolve_model(request, body.model_id)
    result = await chat_router.classify(
        body.message,
        model_policy=model_policy,
        api_base=api_base,
    )

    if result.action == "start_workflow":
        thread_ref = _thread_ref_from_conversation(conversation_id)
        dispatcher = request.app.state.command_dispatcher
        command = StartWorkflow(
            thread_ref=thread_ref,
            workflow_type=result.workflow_type,
            sanitized_messages=(body.message,),
        )
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=result.reply,
        )
        asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
        logger.info(
            "workflow_triggered_from_chat",
            conversation_id=conversation_id,
            workflow_type=result.workflow_type,
        )
    else:
        try:
            reply = await chat_router.reply(
                body.message,
                model_policy=model_policy,
                api_base=api_base,
            )
        except Exception:
            logger.exception("chat_reply_failed")
            reply = "Sorry, I couldn't generate a response right now."
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=reply,
        )

    return conv


@router.get("/chat/conversations")
async def list_conversations(
    store: ChatStoreDep,
    user_id: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List conversations with optional filters."""
    return await store.list_all(user_id=user_id, project_id=project_id)


@router.get("/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    store: ChatStoreDep,
) -> dict[str, Any]:
    """Get a conversation with its message history."""
    conv = await store.get(conversation_id)
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
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    store: ChatStoreDep,
    request: Request,
) -> dict[str, Any]:
    """Send a message to an existing conversation. Routes user messages through the chat router."""
    if body.role not in ("user", "agent", "system"):
        raise HTTPException(
            status_code=422,
            detail="role must be one of: user, agent, system",
        )
    try:
        user_msg = await store.add_message(
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

    # Only route user messages through the chat router
    if body.role != "user":
        return user_msg

    chat_router = getattr(request.app.state, "chat_router", None)
    if chat_router is None:
        return user_msg

    # Use explicit model_id from request, or fall back to conversation's model_id
    effective_model_id = body.model_id
    if effective_model_id is None:
        conv = await store.get(conversation_id)
        if conv is not None:
            effective_model_id = conv.get("model_id")

    model_policy, api_base = await _resolve_model(request, effective_model_id)
    result = await chat_router.classify(
        body.message,
        model_policy=model_policy,
        api_base=api_base,
    )

    if result.action == "start_workflow":
        thread_ref = _thread_ref_from_conversation(conversation_id)
        dispatcher = request.app.state.command_dispatcher
        command = StartWorkflow(
            thread_ref=thread_ref,
            workflow_type=result.workflow_type,
            sanitized_messages=(body.message,),
        )
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=result.reply,
        )
        asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
        logger.info(
            "workflow_triggered_from_chat",
            conversation_id=conversation_id,
            workflow_type=result.workflow_type,
        )
    else:
        try:
            reply = await chat_router.reply(
                body.message,
                model_policy=model_policy,
                api_base=api_base,
            )
        except Exception:
            logger.exception("chat_reply_failed")
            reply = "Sorry, I couldn't generate a response right now."
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=reply,
        )

    return user_msg


@router.post("/chat/conversations/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: str,
    body: SendMessageRequest,
    store: ChatStoreDep,
    request: Request,
) -> StreamingResponse:
    """Send a message and stream the AI response as SSE."""
    if body.role != "user":
        raise HTTPException(status_code=422, detail="Streaming only supports user messages")
    try:
        await store.add_message(
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

    chat_router = getattr(request.app.state, "chat_router", None)

    effective_model_id = body.model_id
    if effective_model_id is None:
        conv = await store.get(conversation_id)
        if conv is not None:
            effective_model_id = conv.get("model_id")

    model_policy, api_base = await _resolve_model(request, effective_model_id)

    async def event_stream() -> AsyncIterator[str]:
        full_content = ""
        if chat_router is None or model_policy is None:
            fallback = "AI responses aren't connected yet. Configure an AI provider."
            yield f"data: {json.dumps({'token': fallback})}\n\n"
            full_content = fallback
        else:
            try:
                result = await chat_router.classify(
                    body.message,
                    model_policy=model_policy,
                    api_base=api_base,
                )
                if result.action == "start_workflow":
                    yield f"data: {json.dumps({'token': result.reply})}\n\n"
                    full_content = result.reply
                    thread_ref = _thread_ref_from_conversation(conversation_id)
                    dispatcher = request.app.state.command_dispatcher
                    command = StartWorkflow(
                        thread_ref=thread_ref,
                        workflow_type=result.workflow_type,
                        sanitized_messages=(body.message,),
                    )
                    asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
                else:
                    async for token in chat_router.reply_stream(
                        body.message,
                        model_policy=model_policy,
                        api_base=api_base,
                    ):
                        full_content += token
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception:
                logger.exception("stream_reply_failed")
                error_msg = "Sorry, I couldn't generate a response right now."
                yield f"data: {json.dumps({'token': error_msg})}\n\n"
                full_content = error_msg

        # Save the complete response
        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=full_content,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete(
    "/chat/conversations/{conversation_id}",
    status_code=204,
)
async def delete_conversation(
    conversation_id: str,
    store: ChatStoreDep,
) -> None:
    """Delete a conversation."""
    if not await store.delete(conversation_id):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
