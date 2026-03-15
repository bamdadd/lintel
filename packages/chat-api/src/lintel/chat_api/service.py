"""ChatService: message classification, project resolution, and workflow dispatch."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

if TYPE_CHECKING:
    from fastapi import Request

    from lintel.chat_api.chat_router import ChatRouterResult
    from lintel.chat_api.store import ChatStore

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.contracts.types import ThreadRef
from lintel.domain.types import (
    Trigger,
    TriggerType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)
from lintel.models.types import ModelPolicy
from lintel.workflows.commands import StartWorkflow
from lintel.workflows.events import WorkflowTriggered
from lintel.workflows.types import PipelineRun, PipelineStatus, Stage

logger = structlog.get_logger()


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
            from lintel.pipelines_api._helpers import _stage_names_for_workflow

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

        from lintel.pipelines_api._helpers import _stage_names_for_workflow

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
        from lintel.workflow_definitions_api.routes import get_workflow_defs

        defs = get_workflow_defs(self._request)
        return {k for k, v in defs.items() if v.get("enabled", True)}

    def is_workflow_enabled(self, workflow_type: str) -> bool:
        """Check if a workflow definition is enabled."""
        from lintel.workflow_definitions_api.routes import get_workflow_defs

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
