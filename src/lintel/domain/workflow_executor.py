"""WorkflowExecutor — wires StartWorkflow commands to LangGraph execution."""

from __future__ import annotations

import time
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


class WorkflowExecutor:
    """Executes a workflow by streaming a LangGraph and emitting events."""

    def __init__(
        self,
        event_store: EventStore,
        graph: Any,  # noqa: ANN401
    ) -> None:
        self._event_store = event_store
        self._graph = graph

    async def execute(self, command: StartWorkflow) -> str:
        run_id = str(uuid4())
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
                {"thread_ref": str(command.thread_ref), "correlation_id": run_id},
                config={"configurable": {"thread_id": run_id}},
            ):
                for node_name, output in chunk.items():
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
