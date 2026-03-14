"""Chat API routes for direct conversation via API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lintel.api.domain.chat_router import ChatRouterResult


from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.commands import StartWorkflow
from lintel.contracts.events import (
    ConversationCreated,
    ConversationDeleted,
    ProjectSelected,
    WorkflowTriggered,
)
from lintel.contracts.types import (
    ModelPolicy,
    PipelineRun,
    PipelineStatus,
    Stage,
    ThreadRef,
    Trigger,
    TriggerType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

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
        from lintel.contracts.data_models import ConversationData

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
        from lintel.contracts.data_models import ChatMessage

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


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_chat_store(request: Request) -> ChatStore:
    return request.app.state.chat_store  # type: ignore[no-any-return]


ChatStoreDep = Annotated[ChatStore, Depends(get_chat_store)]


# ---------------------------------------------------------------------------
# ChatService
# ---------------------------------------------------------------------------


class ChatService:
    """Orchestrates chat message classification, project resolution, and workflow dispatch."""

    def __init__(self, request: Request, store: ChatStore) -> None:
        self._request = request
        self._store = store

    async def resolve_model(
        self,
        model_id: str | None,
    ) -> tuple[ModelPolicy | None, str | None]:
        """Resolve a model_id to a ModelPolicy and api_base.

        Falls back to the default model if no model_id is given.
        Returns (None, None) if no model can be resolved.
        """
        request = self._request
        if model_id is None:
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

        # Merge provider config (e.g. aws_profile_name, aws_region_name) with model config
        extra: dict[str, object] = {}
        if provider.config:
            extra.update(provider.config)
        if model.config:
            extra.update(model.config)
        policy = ModelPolicy(
            provider=provider.provider_type.value,
            model_name=model.model_name,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
            extra_params=extra or None,
        )
        api_base = provider.api_base or None
        return policy, api_base

    async def resolve_project_context(
        self,
        conversation_id: str,
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        """Resolve project, repo URL, and branch for a conversation.

        Returns (project_dict, repo_url, default_branch) or (None, None, None).
        """
        request = self._request
        store = self._store

        conv = await store.get(conversation_id)
        if conv is None:
            return None, None, None

        project_id = conv.get("project_id")
        if not project_id:
            return None, None, None

        project_store = getattr(request.app.state, "project_store", None)
        if project_store is None:
            return None, None, None

        project = await project_store.get(project_id)
        if project is None:
            return None, None, None

        # Resolve first repo
        repo_ids = project.get("repo_ids", ())
        if isinstance(repo_ids, (list, tuple)) and repo_ids:
            repo_store = getattr(request.app.state, "repository_store", None)
            if repo_store is not None:
                repo = await repo_store.get(repo_ids[0])
                if repo is not None:
                    url = repo.url if hasattr(repo, "url") else repo.get("url", "")
                    branch = (
                        repo.default_branch
                        if hasattr(repo, "default_branch")
                        else repo.get("default_branch", "main")
                    )
                    # Resolve all repo URLs for multi-repo support
                    all_urls: list[str] = [url]
                    for rid in repo_ids[1:]:
                        extra = await repo_store.get(rid)
                        if extra is not None:
                            extra_url = extra.url if hasattr(extra, "url") else extra.get("url", "")
                            if extra_url:
                                all_urls.append(extra_url)
                    project["_repo_urls"] = tuple(all_urls)

                    return project, url, branch

        return project, None, project.get("default_branch", "main")

    @staticmethod
    def build_project_context(
        project: dict[str, Any] | None,
        repo_url: str | None = None,
        default_branch: str | None = None,
    ) -> str:
        """Build a project context string for the AI system prompt."""
        if project is None:
            return ""
        parts = [
            "PROJECT CONTEXT — You are working on the following project:",
            f"  Project name: {project.get('name', 'unknown')}",
            f"  Project ID: {project.get('project_id', 'unknown')}",
        ]
        if repo_url:
            parts.append(f"  Repository: {repo_url}")
        repo_urls = project.get("_repo_urls")
        if repo_urls and len(repo_urls) > 1:
            parts.append(f"  All repositories: {', '.join(repo_urls)}")
        if default_branch:
            parts.append(f"  Default branch: {default_branch}")
        status = project.get("status", "")
        if status:
            parts.append(f"  Status: {status}")
        parts.append(
            "\nUse this project context when answering questions. "
            "You know which project the user is working on."
        )
        return "\n".join(parts)

    async def prompt_project_selection(self, conversation_id: str) -> str:
        """Build a message prompting the user to select a project."""
        request = self._request
        project_store = getattr(request.app.state, "project_store", None)
        if project_store is None:
            return "No projects configured. Please create a project first."

        projects = await project_store.list_all()
        if not projects:
            return "No projects found. Please create a project first at Settings > Projects."

        lines = ["Which project is this for?\n"]
        for i, p in enumerate(projects, 1):
            name = p.get("name", p.get("project_id", "unknown"))
            lines.append(f"  **{i}.** {name}")
        lines.append("\nReply with the project name or number.")
        return "\n".join(lines)

    async def try_select_project(self, conversation_id: str, message: str) -> bool:
        """Try to match user reply to a project. Returns True if matched."""
        request = self._request
        store = self._store

        project_store = getattr(request.app.state, "project_store", None)
        if project_store is None:
            return False

        projects = await project_store.list_all()
        if not projects:
            return False

        lower = message.strip().lower()

        # Try numeric selection
        try:
            idx = int(lower) - 1
            if 0 <= idx < len(projects):
                pid = projects[idx].get("project_id", projects[idx].get("name"))
                await store.update_fields(conversation_id, project_id=pid)
                return True
        except ValueError:
            pass

        # Try name match
        for p in projects:
            name = p.get("name", "")
            if name.lower() == lower or p.get("project_id", "").lower() == lower:
                pid = p.get("project_id", p.get("name"))
                await store.update_fields(conversation_id, project_id=pid)
                return True

        return False

    async def dispatch_workflow(
        self,
        conversation_id: str,
        workflow_type: str,
        message: str,
        reply_text: str,
    ) -> None:
        """Create a work item, resolve project context, and dispatch the workflow."""
        request = self._request
        store = self._store

        thread_ref = self.thread_ref_from_conversation(conversation_id)
        dispatcher = request.app.state.command_dispatcher

        # Resolve project and repo context
        project, repo_url, repo_branch = await self.resolve_project_context(conversation_id)

        # Create a work item
        work_item_id = uuid4().hex
        work_item_store = getattr(request.app.state, "work_item_store", None)
        if work_item_store is not None and project is not None:
            work_item = WorkItem(
                work_item_id=work_item_id,
                project_id=project.get("project_id", ""),
                title=message[:100],
                description=message,
                work_type=self.infer_work_type(workflow_type),
                status=WorkItemStatus.IN_PROGRESS,
                thread_ref_str=str(thread_ref),
                branch_name=f"lintel/feat/{work_item_id[:8]}",
            )
            try:
                await work_item_store.add(work_item)
            except Exception:
                logger.warning("work_item_creation_failed", work_item_id=work_item_id)

        # Create Trigger and PipelineRun records
        project_id = project.get("project_id", "") if project else ""
        run_id = uuid4().hex
        trigger_id = uuid4().hex

        trigger_store = getattr(request.app.state, "trigger_store", None)
        if trigger_store is not None and project_id:
            trigger = Trigger(
                trigger_id=trigger_id,
                project_id=project_id,
                trigger_type=TriggerType.CHAT,
                name=f"chat:{conversation_id}",
            )
            try:
                await trigger_store.add(trigger)
            except Exception:
                logger.warning("trigger_creation_failed", trigger_id=trigger_id)

        pipeline_store = getattr(request.app.state, "pipeline_store", None)
        if pipeline_store is not None and project_id:
            from lintel.api.routes.pipelines import _stage_names_for_workflow

            stage_names = _stage_names_for_workflow(workflow_type)
            stages = tuple(
                Stage(
                    stage_id=uuid4().hex,
                    name=name,
                    stage_type=name,
                )
                for name in stage_names
            )
            pipeline_run = PipelineRun(
                run_id=run_id,
                project_id=project_id,
                work_item_id=work_item_id,
                workflow_definition_id=workflow_type,
                status=PipelineStatus.RUNNING,
                trigger_type=f"chat:{conversation_id}",
                trigger_id=trigger_id,
                stages=stages,
                created_at=datetime.now(UTC).isoformat(),
            )
            try:
                await pipeline_store.add(pipeline_run)
            except Exception:
                logger.warning("pipeline_run_creation_failed", run_id=run_id)

        # Store workflow tracking IDs on the conversation for status queries
        await store.update_fields(conversation_id, work_item_id=work_item_id, run_id=run_id)

        # Gather repo context for the command
        cmd_repo_url = repo_url or ""
        cmd_repo_urls = project.get("_repo_urls", ()) if project else ()
        cmd_repo_branch = repo_branch or "main"
        cmd_credential_ids = tuple(project.get("credential_ids", ())) if project else ()

        command = StartWorkflow(
            thread_ref=thread_ref,
            workflow_type=workflow_type,
            sanitized_messages=(message,),
            project_id=project_id,
            work_item_id=work_item_id,
            run_id=run_id,
            repo_url=cmd_repo_url,
            repo_urls=(cmd_repo_urls if isinstance(cmd_repo_urls, tuple) else tuple(cmd_repo_urls)),
            repo_branch=cmd_repo_branch,
            credential_ids=cmd_credential_ids,
        )

        # Build a rich status message with project context and workflow stages
        project_name = project.get("name", "unknown") if project else "unknown"
        status_lines = [reply_text, ""]
        status_lines.append(f"**Project:** {project_name}")
        if cmd_repo_url:
            status_lines.append(f"**Repository:** {cmd_repo_url}")
        status_lines.append(f"**Branch:** {cmd_repo_branch}")
        status_lines.append("")
        status_lines.append("**Workflow stages:**")

        from lintel.api.routes.pipelines import _stage_names_for_workflow

        for stage_name in _stage_names_for_workflow(workflow_type):
            status_lines.append(f"  ⏳ {stage_name}")

        status_lines.append("")
        status_lines.append(f"[View pipeline →](/pipelines/{run_id})")
        status_lines.append("")
        status_lines.append("I'll update you as each stage completes.")

        await store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content="\n".join(status_lines),
        )
        asyncio.create_task(dispatcher.dispatch(command))  # noqa: RUF006
        logger.info(
            "workflow_triggered_from_chat",
            conversation_id=conversation_id,
            workflow_type=workflow_type,
            project_id=project_id,
            work_item_id=work_item_id,
            run_id=run_id,
        )

        await dispatch_event(
            request,
            WorkflowTriggered(
                payload={
                    "resource_id": work_item_id,
                    "workflow_type": workflow_type,
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "run_id": run_id,
                }
            ),
            stream_id=f"conversation:{conversation_id}",
        )

    def get_enabled_workflows(self) -> set[str]:
        """Return set of enabled workflow definition IDs."""
        from lintel.api.routes.workflow_definitions import get_workflow_defs

        defs = get_workflow_defs(self._request)
        return {k for k, v in defs.items() if v.get("enabled", True)}

    def is_workflow_enabled(self, workflow_type: str) -> bool:
        """Check if a workflow definition is enabled."""
        from lintel.api.routes.workflow_definitions import get_workflow_defs

        defs = get_workflow_defs(self._request)
        wf = defs.get(workflow_type)
        if wf is None:
            return False
        return bool(wf.get("enabled", True))

    @staticmethod
    def infer_work_type(workflow_type: str) -> WorkItemType:
        """Map workflow type string to WorkItemType."""
        mapping = {
            "feature_to_pr": WorkItemType.FEATURE,
            "bug_fix": WorkItemType.BUG,
            "refactor": WorkItemType.REFACTOR,
        }
        return mapping.get(workflow_type, WorkItemType.TASK)

    @staticmethod
    def thread_ref_from_conversation(conversation_id: str) -> ThreadRef:
        """Map a chat conversation to a ThreadRef for workflow dispatch."""
        return ThreadRef(
            workspace_id="lintel-chat",
            channel_id="chat",
            thread_ts=conversation_id,
        )

    async def handle_classified_message(
        self,
        conversation_id: str,
        message: str,
        classify_result: object,
        model_policy: object,
        api_base: str | None,
    ) -> str | None:
        """Handle a classified message: dispatch workflow or generate reply.

        Returns the reply text, or None if a workflow was dispatched
        (in which case dispatch_workflow already added the message).
        """
        result: ChatRouterResult = classify_result  # type: ignore[assignment]

        if result.action == "start_workflow":
            # Check if the workflow is enabled
            workflow_enabled = self.is_workflow_enabled(result.workflow_type)
            if not workflow_enabled:
                logger.info(
                    "workflow_disabled_fallback_to_chat",
                    workflow_type=result.workflow_type,
                )
                # Fall through to chat/MCP reply instead
                pass
            else:
                conv_data = await self._store.get(conversation_id)
                if conv_data and not conv_data.get("project_id"):
                    prompt_msg = await self.prompt_project_selection(conversation_id)
                    await self._store.add_message(
                        conversation_id,
                        user_id="system",
                        display_name="Lintel",
                        role="agent",
                        content=prompt_msg,
                    )
                    await self._store.update_fields(
                        conversation_id,
                        _pending_workflow={
                            "workflow_type": result.workflow_type,
                            "message": message,
                            "reply": result.reply,
                        },
                    )
                    return None
                await self.dispatch_workflow(
                    conversation_id,
                    result.workflow_type,
                    message,
                    result.reply,
                )
                return None

        # Chat reply path — resolve project context for the LLM
        project, repo_url, branch = await self.resolve_project_context(conversation_id)
        proj_ctx = self.build_project_context(project, repo_url, branch)
        chat_router = self._request.app.state.chat_router
        try:
            reply: str = await chat_router.reply(
                message,
                model_policy=model_policy,
                api_base=api_base,
                project_context=proj_ctx,
            )
        except Exception:
            logger.exception("chat_reply_failed")
            reply = "Sorry, I couldn't generate a response right now."
        await self._store.add_message(
            conversation_id,
            user_id="system",
            display_name="Lintel",
            role="agent",
            content=reply,
        )
        return reply


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
        enabled_workflows=svc.get_enabled_workflows(),
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
        enabled_workflows=svc.get_enabled_workflows(),
    )

    await svc.handle_classified_message(
        conversation_id,
        body.message,
        result,
        model_policy,
        api_base,
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

    svc = ChatService(request, store)
    model_policy, api_base = await svc.resolve_model(effective_model_id)

    async def event_stream() -> AsyncIterator[str]:
        full_content = ""
        workflow_dispatched = False
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
                    enabled_workflows=svc.get_enabled_workflows(),
                )
                if result.action == "start_workflow":
                    workflow_dispatched = True
                    # Use shared handler (creates work item, pipeline, messages)
                    await svc.handle_classified_message(
                        conversation_id,
                        body.message,
                        result,
                        model_policy,
                        api_base,
                    )
                    # Stream the last agent message back to the client
                    conv_after = await store.get(conversation_id)
                    if conv_after:
                        agent_msgs = [
                            m for m in conv_after.get("messages", []) if m.get("role") == "agent"
                        ]
                        if agent_msgs:
                            full_content = agent_msgs[-1]["content"]
                            yield f"data: {json.dumps({'token': full_content})}\n\n"
                else:
                    # Stream reply token-by-token for chat responses
                    project, repo_url, branch = await svc.resolve_project_context(conversation_id)
                    proj_ctx = svc.build_project_context(project, repo_url, branch)
                    async for token in chat_router.reply_stream(
                        body.message,
                        model_policy=model_policy,
                        api_base=api_base,
                        project_context=proj_ctx,
                    ):
                        full_content += token
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception:
                logger.exception("stream_reply_failed")
                error_msg = "Sorry, I couldn't generate a response right now."
                yield f"data: {json.dumps({'token': error_msg})}\n\n"
                full_content = error_msg

        # Save the complete response (skip if workflow already saved it)
        if full_content and not workflow_dispatched:
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


@router.get("/chat/conversations/{conversation_id}/events")
async def stream_conversation_events(
    conversation_id: str,
    store: ChatStoreDep,
) -> StreamingResponse:
    """Stream new chat messages via SSE for real-time updates."""
    conv = await store.get(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )

    async def event_stream() -> AsyncIterator[str]:
        last_count = 0
        while True:
            conv = await store.get(conversation_id)
            if conv is None:
                return
            messages = conv.get("messages", [])
            current_count = len(messages)
            if current_count > last_count:
                for msg in messages[last_count:]:
                    yield f"data: {json.dumps(msg)}\n\n"
                last_count = current_count
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
