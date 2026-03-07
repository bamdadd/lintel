"""WorkflowExecutor — wires StartWorkflow commands to LangGraph execution."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.contracts.events import (
    PipelineRunCompleted,
    PipelineRunFailed,
    PipelineRunStarted,
    PipelineStageCompleted,
)

if TYPE_CHECKING:
    from lintel.contracts.commands import StartWorkflow
    from lintel.contracts.protocols import EventStore

def _dict_to_stage(d: dict[str, Any]) -> Any:
    """Convert a plain dict to a Stage dataclass instance."""
    from dataclasses import fields as dc_fields

    from lintel.contracts.types import Stage, StageStatus

    valid = {f.name for f in dc_fields(Stage)}
    filtered = {k: v for k, v in d.items() if k in valid}
    # Convert string status to enum
    if "status" in filtered and isinstance(filtered["status"], str):
        try:
            filtered["status"] = StageStatus(filtered["status"])
        except ValueError:
            pass
    return Stage(**filtered)


# Callback signature: (node_name, phase_label) -> None
StageCallback = Callable[[str, str], Awaitable[None]]


class WorkflowExecutor:
    """Executes a workflow by streaming a LangGraph and emitting events."""

    def __init__(
        self,
        event_store: EventStore,
        graph: Any = None,  # noqa: ANN401 — legacy single graph
        agent_runtime: Any = None,  # noqa: ANN401
        on_stage_complete: StageCallback | None = None,
        app_state: Any = None,  # noqa: ANN401
        graph_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._event_store = event_store
        self._graph = graph
        self._agent_runtime = agent_runtime
        self._on_stage_complete = on_stage_complete
        self._app_state = app_state
        self._graph_factory = graph_factory

    async def execute(self, command: StartWorkflow) -> str:
        run_id = command.run_id or str(uuid4())
        stream_id = f"run:{run_id}"

        await self._event_store.append(
            stream_id=stream_id,
            events=[
                PipelineRunStarted(
                    event_type="PipelineRunStarted",
                    payload={
                        "pipeline_id": command.workflow_type,
                        "run_id": run_id,
                        "trigger_type": "command",
                        "thread_ref": str(command.thread_ref),
                    },
                )
            ],
        )

        # Mark first stage as running
        await self._mark_first_stage_running(run_id)

        # Resolve graph: prefer factory (per workflow type), fall back to static graph
        graph = self._graph
        if self._graph_factory is not None:
            graph = self._graph_factory(command.workflow_type)

        total_tokens: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        try:
            async for chunk in graph.astream(
                {
                    "thread_ref": str(command.thread_ref),
                    "correlation_id": run_id,
                    "sanitized_messages": list(command.sanitized_messages),
                    "project_id": command.project_id,
                    "work_item_id": command.work_item_id,
                    "run_id": run_id,
                    "repo_url": command.repo_url,
                    "repo_urls": command.repo_urls,
                    "repo_branch": command.repo_branch,
                    "credential_ids": command.credential_ids,
                },
                config={
                    "configurable": {
                        "thread_id": run_id,
                        "run_id": run_id,
                        "agent_runtime": self._agent_runtime,
                        "app_state": self._app_state,
                        "sandbox_manager": getattr(self._app_state, "sandbox_manager", None),
                        "credential_store": getattr(self._app_state, "credential_store", None),
                        "code_artifact_store": getattr(self._app_state, "code_artifact_store", None),
                        "test_result_store": getattr(self._app_state, "test_result_store", None),
                    }
                },
            ):
                for node_name, output in chunk.items():
                    phase = output.get("current_phase", node_name) if isinstance(output, dict) else node_name
                    timestamp_ms = int(time.time() * 1000)
                    await self._event_store.append(
                        stream_id=stream_id,
                        events=[
                            PipelineStageCompleted(
                                event_type="PipelineStageCompleted",
                                payload={
                                    "run_id": run_id,
                                    "node_name": node_name,
                                    "output": output,
                                    "timestamp_ms": timestamp_ms,
                                },
                            )
                        ],
                    )
                    await self._mark_stage_completed(run_id, node_name, timestamp_ms)

                    # Accumulate token usage from node output
                    if isinstance(output, dict):
                        for entry in output.get("token_usage", []):
                            if isinstance(entry, dict):
                                total_tokens["input_tokens"] += entry.get("input_tokens", 0)
                                total_tokens["output_tokens"] += entry.get("output_tokens", 0)
                                total_tokens["total_tokens"] += entry.get("total_tokens", 0)

                    # Build stage completion message
                    is_approval = "approve" in node_name or "approval" in node_name
                    if is_approval:
                        await self._notify_chat(
                            run_id,
                            f"⏸️ **{node_name}** — auto-approved (noop mode)\n"
                            f"[View pipeline →](/pipelines/{run_id})",
                        )
                    elif node_name == "plan" and isinstance(output, dict):
                        # Show plan details in chat
                        plan = output.get("plan", {})
                        if isinstance(plan, dict) and plan.get("tasks"):
                            lines = [f"✅ **plan** completed\n"]
                            summary = plan.get("summary", "")
                            if summary:
                                lines.append(f"**Summary:** {summary}\n")
                            lines.append("**Tasks:**")
                            for i, task in enumerate(plan.get("tasks", []), 1):
                                title = task.get("title", task) if isinstance(task, dict) else str(task)
                                lines.append(f"  {i}. {title}")
                            await self._notify_chat(run_id, "\n".join(lines))
                        else:
                            await self._notify_chat(run_id, f"✅ **{node_name}** completed")
                    else:
                        await self._notify_chat(
                            run_id,
                            f"✅ **{node_name}** completed",
                        )

                    if self._on_stage_complete is not None:
                        try:
                            await self._on_stage_complete(node_name, phase)
                        except Exception:
                            pass  # don't let notification failures break the workflow

            await self._event_store.append(
                stream_id=stream_id,
                events=[
                    PipelineRunCompleted(
                        event_type="PipelineRunCompleted",
                        payload={"run_id": run_id, "status": "succeeded", "token_usage": total_tokens},
                    )
                ],
            )
            await self._update_pipeline_status(run_id, "succeeded")
            await self._complete_work_item(command)
            token_summary = ""
            if total_tokens["total_tokens"] > 0:
                token_summary = (
                    f"\n📊 Tokens: {total_tokens['total_tokens']:,} "
                    f"({total_tokens['input_tokens']:,} in / "
                    f"{total_tokens['output_tokens']:,} out)"
                )
            await self._notify_chat(
                run_id,
                f"🎉 **Workflow completed successfully**{token_summary}\n"
                f"[View pipeline →](/pipelines/{run_id})",
            )
        except Exception as exc:
            await self._mark_running_stages_failed(run_id, str(exc))
            await self._event_store.append(
                stream_id=stream_id,
                events=[
                    PipelineRunFailed(
                        event_type="PipelineRunFailed",
                        payload={"run_id": run_id, "error": str(exc)},
                    )
                ],
            )
            await self._update_pipeline_status(run_id, "failed")
            await self._fail_work_item(command)
            await self._notify_chat(
                run_id,
                f"❌ **Workflow failed**: {exc}\n"
                f"[View pipeline →](/pipelines/{run_id})",
            )

        return run_id

    async def _notify_chat(self, run_id: str, message: str) -> None:
        """Post a status message to the chat conversation linked to this pipeline."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        chat_store = getattr(self._app_state, "chat_store", None)
        if pipeline_store is None or chat_store is None:
            return
        try:
            run = await pipeline_store.get(run_id)
            if run is None:
                return
            trigger = run.trigger_type
            if not trigger.startswith("chat:"):
                return
            conversation_id = trigger[5:]  # strip "chat:" prefix
            await chat_store.add_message(
                conversation_id,
                user_id="system",
                display_name="Lintel",
                role="agent",
                content=message,
            )
        except Exception:
            pass

    async def _mark_stage_completed(
        self, run_id: str, node_name: str, timestamp_ms: int,
    ) -> None:
        """Mark a pipeline stage as completed in the store."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        try:
            from dataclasses import replace
            from datetime import UTC, datetime

            from lintel.contracts.types import StageStatus

            run = await pipeline_store.get(run_id)
            if run is None:
                return
            finished = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()
            updated_stages = []
            found = False
            for stage in run.stages:
                # Handle both Stage dataclass instances and plain dicts (Postgres)
                if isinstance(stage, dict):
                    stage = _dict_to_stage(stage)
                s_name = stage.name
                s_type = stage.stage_type
                if s_name == node_name or s_type == node_name:
                    started = stage.started_at or finished
                    duration = 0
                    if stage.started_at:
                        start_ts = datetime.fromisoformat(stage.started_at).timestamp()
                        duration = timestamp_ms - int(start_ts * 1000)
                    updated_stages.append(replace(
                        stage,
                        status=StageStatus.SUCCEEDED,
                        started_at=started,
                        finished_at=finished,
                        duration_ms=duration,
                    ))
                    found = True
                else:
                    updated_stages.append(stage)
            # Mark the next stage as running
            if found:
                for i, s in enumerate(updated_stages):
                    if isinstance(s, dict):
                        s = _dict_to_stage(s)
                    if s.status == StageStatus.SUCCEEDED:
                        continue
                    if s.status == StageStatus.PENDING:
                        updated_stages[i] = replace(s, status=StageStatus.RUNNING, started_at=finished)
                        break
            updated = replace(run, stages=tuple(updated_stages))
            await pipeline_store.update(updated)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("mark_stage_completed_failed", run_id=run_id, node_name=node_name, error=str(exc))

    async def _update_pipeline_status(self, run_id: str, status: str) -> None:
        """Update the pipeline run status in the pipeline store."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        try:
            from dataclasses import replace

            run = await pipeline_store.get(run_id)
            if run is not None:
                from lintel.contracts.types import PipelineStatus

                new_status = PipelineStatus(status)
                updated = replace(run, status=new_status)
                await pipeline_store.update(updated)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("update_pipeline_status_failed", run_id=run_id, status=status, error=str(exc))

    async def _mark_first_stage_running(self, run_id: str) -> None:
        """Mark the first pipeline stage as running."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        try:
            from dataclasses import replace
            from datetime import UTC, datetime

            from lintel.contracts.types import StageStatus

            run = await pipeline_store.get(run_id)
            if run is None or not run.stages:
                return
            stages = list(run.stages)
            first = stages[0]
            if isinstance(first, dict):
                first = _dict_to_stage(first)
            now = datetime.now(UTC).isoformat()
            stages[0] = replace(first, status=StageStatus.RUNNING, started_at=now)
            updated = replace(run, stages=tuple(stages))
            await pipeline_store.update(updated)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("mark_first_stage_running_failed", run_id=run_id, error=str(exc))

    async def _mark_running_stages_failed(self, run_id: str, error: str) -> None:
        """Mark any stages still in 'running' status as failed when the workflow errors."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        try:
            from dataclasses import replace

            from lintel.contracts.types import StageStatus

            run = await pipeline_store.get(run_id)
            if run is None:
                return
            updated_stages = []
            changed = False
            for stage in run.stages:
                if isinstance(stage, dict):
                    stage = _dict_to_stage(stage)
                if stage.status == StageStatus.RUNNING:
                    updated_stages.append(replace(stage, status=StageStatus.FAILED, error=error))
                    changed = True
                else:
                    updated_stages.append(stage)
            if changed:
                updated = replace(run, stages=tuple(updated_stages))
                await pipeline_store.update(updated)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning(
                "mark_running_stages_failed_error", run_id=run_id, error=str(exc),
            )

    async def _fail_work_item(self, command: StartWorkflow) -> None:
        """Mark the work item as failed after workflow failure."""
        if self._app_state is None:
            return
        work_item_store = getattr(self._app_state, "work_item_store", None)
        if work_item_store is None or not command.work_item_id:
            return
        try:
            item = await work_item_store.get(command.work_item_id)
            if item is None:
                return
            item["status"] = "failed"
            await work_item_store.update(command.work_item_id, item)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning(
                "fail_work_item_failed",
                work_item_id=command.work_item_id,
                error=str(exc),
            )

    async def _complete_work_item(self, command: StartWorkflow) -> None:
        """Mark the work item as closed after workflow success."""
        if self._app_state is None:
            return
        work_item_store = getattr(self._app_state, "work_item_store", None)
        if work_item_store is None or not command.work_item_id:
            return
        try:
            item = await work_item_store.get(command.work_item_id)
            if item is None:
                return
            item["status"] = "closed"
            await work_item_store.update(command.work_item_id, item)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("complete_work_item_failed", work_item_id=command.work_item_id, error=str(exc))
