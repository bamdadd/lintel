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
    ) -> None:
        self._event_store = event_store
        self._graph = graph
        self._agent_runtime = agent_runtime
        self._on_stage_complete = on_stage_complete

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
                        "agent_runtime": self._agent_runtime,
                    }
                },
            ):
                for node_name, output in chunk.items():
                    phase = output.get("current_phase", node_name) if isinstance(output, dict) else node_name
                    await self._event_store.append(
                        stream_id=stream_id,
                        events=[
                            PipelineStageCompleted(
                                event_type="PipelineStageCompleted",
                                payload={
                                    "run_id": run_id,
                                    "node_name": node_name,
                                    "output": output,
                                    "timestamp_ms": int(time.time() * 1000),
                                },
                            )
                        ],
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

        return run_id
