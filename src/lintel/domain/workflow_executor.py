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
        graph: Any,  # noqa: ANN401
        agent_runtime: Any = None,  # noqa: ANN401
        on_stage_complete: StageCallback | None = None,
        app_state: Any = None,  # noqa: ANN401
    ) -> None:
        self._event_store = event_store
        self._graph = graph
        self._agent_runtime = agent_runtime
        self._on_stage_complete = on_stage_complete
        self._app_state = app_state

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

        try:
            async for chunk in self._graph.astream(
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

                    # Check if this is an approval stage
                    is_approval = "approve" in node_name or "approval" in node_name
                    if is_approval:
                        await self._notify_chat(
                            run_id,
                            f"⏸️ **{node_name}** — auto-approved (noop mode)\n"
                            f"[View pipeline →](/pipelines/{run_id})",
                        )
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
                        payload={"run_id": run_id, "status": "succeeded"},
                    )
                ],
            )
            await self._update_pipeline_status(run_id, "succeeded")
            await self._notify_chat(
                run_id,
                f"🎉 **Workflow completed successfully**\n"
                f"[View pipeline →](/pipelines/{run_id})",
            )
        except Exception as exc:
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
                else:
                    updated_stages.append(stage)
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
        except Exception:
            import structlog
            structlog.get_logger().warning("update_pipeline_status_failed", run_id=run_id, status=status, error=str(exc))
