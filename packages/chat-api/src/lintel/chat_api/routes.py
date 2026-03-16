"""Chat API routes for direct conversation via API."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
import structlog

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider

# ---------------------------------------------------------------------------
# Re-exports — keep backward compatibility for importers of this module
# ---------------------------------------------------------------------------
from lintel.chat_api.models import SendMessageRequest, StartConversationRequest
from lintel.chat_api.service import ChatService
from lintel.chat_api.store import ChatStore
from lintel.chat_api.streaming import streaming_router
from lintel.domain.events import (
    ConversationCreated,
    ConversationDeleted,
    ProjectSelected,
)
from lintel.workflows.types import PipelineStatus

__all__ = [
    "ChatService",
    "ChatStore",
    "SendMessageRequest",
    "StartConversationRequest",
    "chat_store_provider",
    "router",
    "streaming_router",
]

logger = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Store dependency
# ---------------------------------------------------------------------------


def get_chat_store(request: Request) -> ChatStore:
    return request.app.state.chat_store  # type: ignore[no-any-return]


chat_store_provider: StoreProvider[ChatStore] = StoreProvider()

ChatStoreDep = Annotated[ChatStore, Depends(get_chat_store)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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
    await dispatch_event(
        request,
        ConversationCreated(
            payload={
                "resource_id": conversation_id,
                "user_id": body.user_id,
                "project_id": body.project_id or "",
            }
        ),
        stream_id=f"conversation:{conversation_id}",
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

    svc = ChatService(request, store)
    model_policy, api_base = await svc.resolve_model(body.model_id)
    result = await chat_router.classify(
        body.message,
        model_policy=model_policy,
        api_base=api_base,
        enabled_workflows=await svc.get_enabled_workflows(),
    )

    await svc.handle_classified_message(
        conversation_id,
        body.message,
        result,
        model_policy,
        api_base,
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

    svc = ChatService(request, store)

    # Check if there's a pending workflow awaiting project selection
    conv = await store.get(conversation_id)
    pending = conv.get("_pending_workflow") if conv else None
    if pending:
        # User is replying to project selection prompt
        matched = await svc.try_select_project(conversation_id, body.message)
        if matched:
            updated_conv = await store.get(conversation_id)
            selected_project_id = updated_conv.get("project_id", "") if updated_conv else ""
            await dispatch_event(
                request,
                ProjectSelected(
                    payload={"resource_id": conversation_id, "project_id": selected_project_id},
                    actor_id=body.user_id,
                ),
                stream_id=f"conversation:{conversation_id}",
            )
            await store.update_fields(conversation_id, _pending_workflow=None)
            await svc.dispatch_workflow(
                conversation_id,
                pending["workflow_type"],
                pending["message"],
                pending["reply"],
            )
        else:
            await store.add_message(
                conversation_id,
                user_id="system",
                display_name="Lintel",
                role="agent",
                content="I didn't recognise that project. "
                "Please reply with the project name or number.",
            )
        return user_msg

    model_policy, api_base = await svc.resolve_model(effective_model_id)
    result = await chat_router.classify(
        body.message,
        model_policy=model_policy,
        api_base=api_base,
        enabled_workflows=await svc.get_enabled_workflows(),
    )

    await svc.handle_classified_message(
        conversation_id,
        body.message,
        result,
        model_policy,
        api_base,
    )

    return user_msg


@router.get("/chat/conversations/{conversation_id}/status")
async def get_conversation_status(
    conversation_id: str,
    store: ChatStoreDep,
) -> dict[str, Any]:
    """Return workflow status for a conversation (project, work item, run)."""
    conv = await store.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
    return {
        "conversation_id": conversation_id,
        "project_id": conv.get("project_id"),
        "work_item_id": conv.get("work_item_id"),
        "run_id": conv.get("run_id"),
    }


@router.post("/chat/conversations/{conversation_id}/retry", status_code=200)
async def retry_workflow(
    conversation_id: str,
    store: ChatStoreDep,
    request: Request,
) -> dict[str, Any]:
    """Retry a failed workflow from the last checkpoint."""
    conv = await store.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )

    pending = conv.get("_pending_workflow")
    run_id = conv.get("run_id")

    if not pending and not run_id:
        raise HTTPException(
            status_code=409,
            detail="No workflow associated with this conversation",
        )

    # If there's a run_id, verify the pipeline is in a failed state
    if run_id and not pending:
        pipeline_store = getattr(request.app.state, "pipeline_store", None)
        if pipeline_store is not None:
            pipeline_run = await pipeline_store.get(run_id)
            if pipeline_run is not None:
                status = (
                    pipeline_run.status
                    if hasattr(pipeline_run, "status")
                    else pipeline_run.get("status", "")
                )
                status_str = str(status)
                if status_str not in ("failed", PipelineStatus.FAILED):
                    raise HTTPException(
                        status_code=409,
                        detail=f"Pipeline is {status_str}, not failed",
                    )

    # Determine workflow parameters
    if pending:
        workflow_type = pending["workflow_type"]
        message = pending["message"]
        reply_text = pending.get("reply", "Retrying workflow...")
    else:
        # Re-dispatch using stored conversation data
        messages = conv.get("messages", [])
        user_msgs = [m for m in messages if m.get("role") == "user"]
        message = user_msgs[-1]["content"] if user_msgs else ""
        workflow_type = "feature_to_pr"
        reply_text = "Retrying workflow..."

    await store.add_message(
        conversation_id,
        user_id="system",
        display_name="Lintel",
        role="agent",
        content="Retrying workflow...",
    )

    svc = ChatService(request, store)
    await svc.dispatch_workflow(
        conversation_id,
        workflow_type,
        message,
        reply_text,
    )

    return await store.get(conversation_id)  # type: ignore[return-value]


@router.delete(
    "/chat/conversations/{conversation_id}",
    status_code=204,
)
async def delete_conversation(
    conversation_id: str,
    store: ChatStoreDep,
    request: Request,
) -> None:
    """Delete a conversation."""
    deleted = await store.delete(conversation_id)
    if deleted:
        await dispatch_event(
            request,
            ConversationDeleted(payload={"resource_id": conversation_id}),
            stream_id=f"conversation:{conversation_id}",
        )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
