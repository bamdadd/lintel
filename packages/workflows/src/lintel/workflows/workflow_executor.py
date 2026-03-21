"""WorkflowExecutor — wires StartWorkflow commands to LangGraph execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.workflows._executor_artifacts import (
    auto_promote_if_capacity as _auto_promote_if_capacity,
)
from lintel.workflows._executor_artifacts import (
    complete_work_item as _complete_work_item,
)
from lintel.workflows._executor_artifacts import (
    create_approval_request as _create_approval_request,
)
from lintel.workflows._executor_artifacts import (
    evaluate_policy as _evaluate_policy,
)
from lintel.workflows._executor_artifacts import (
    fail_work_item as _fail_work_item,
)
from lintel.workflows._executor_artifacts import (
    rehydrate_from_run as _rehydrate_from_run,
)
from lintel.workflows._executor_lifecycle import (
    determine_final_status as _determine_final_status,
)
from lintel.workflows._executor_lifecycle import (
    get_stage_id as _get_stage_id,
)
from lintel.workflows._executor_lifecycle import (
    mark_first_stage_running as _mark_first_stage_running,
)
from lintel.workflows._executor_lifecycle import (
    mark_running_stages_failed as _mark_running_stages_failed,
)
from lintel.workflows._executor_lifecycle import (
    mark_stage_completed as _mark_stage_completed,
)
from lintel.workflows._executor_lifecycle import (
    mark_stage_timed_out as _mark_stage_timed_out,
)
from lintel.workflows._executor_lifecycle import (
    mark_stage_waiting_approval as _mark_stage_waiting_approval,
)
from lintel.workflows._executor_lifecycle import (
    notify_chat as _notify_chat,
)
from lintel.workflows._executor_lifecycle import (
    send_stage_notification as _send_stage_notification,
)
from lintel.workflows._executor_lifecycle import (
    update_pipeline_status as _update_pipeline_status,
)
from lintel.workflows.events import (
    PipelineRunCompleted,
    PipelineRunFailed,
    PipelineRunStarted,
    PipelineStageCompleted,
    PipelineStageTimedOut,
    WorkflowQueued,
)
from lintel.workflows.timeout import resolve_timeout

if TYPE_CHECKING:
    from lintel.contracts.protocols import EventStore
    from lintel.observability.protocols import StepMetricsRecorder
    from lintel.workflows.commands import StartWorkflow
    from lintel.workflows.types import Stage

logger = structlog.get_logger()


def _dict_to_stage(d: dict[str, Any]) -> Stage:
    """Convert a plain dict to a Stage dataclass instance."""
    from dataclasses import fields as dc_fields

    from lintel.workflows.types import Stage, StageStatus

    valid = {f.name for f in dc_fields(Stage)}
    filtered = {k: v for k, v in d.items() if k in valid}
    # Convert string status to enum
    if "status" in filtered and isinstance(filtered["status"], str):
        with contextlib.suppress(ValueError):
            filtered["status"] = StageStatus(filtered["status"])
    return Stage(**filtered)


# Callback signature: (node_name, phase_label) -> None
StageCallback = Callable[[str, str], Awaitable[None]]


class WorkflowExecutor:
    """Executes a workflow by streaming a LangGraph and emitting events.

    Supports LangGraph interrupt_before for human-in-the-loop approval gates.
    When the graph pauses at an interrupt, the executor marks the next stage as
    waiting_approval and stores the graph reference. Call ``resume(run_id)`` after
    the stage is approved to continue execution.
    """

    def __init__(
        self,
        event_store: EventStore,
        graph: Any = None,  # noqa: ANN401 — legacy single graph
        agent_runtime: Any = None,  # noqa: ANN401
        on_stage_complete: StageCallback | None = None,
        app_state: Any = None,  # noqa: ANN401
        graph_factory: Callable[[str], Any] | None = None,
        step_metrics: StepMetricsRecorder | None = None,
        max_concurrent_workflows: int = 10,
    ) -> None:
        self._event_store = event_store
        self._graph = graph
        self._agent_runtime = agent_runtime
        self._on_stage_complete = on_stage_complete
        self._app_state = app_state
        self._graph_factory = graph_factory
        self._step_metrics = step_metrics
        # Store compiled graphs and configs per run_id for resumption
        self._suspended_runs: dict[str, dict[str, Any]] = {}
        # Semaphore-gated concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent_workflows)
        self._max_concurrent_workflows = max_concurrent_workflows
        self._queue_depth = 0

    async def _project_events(self, events: list[Any]) -> None:
        """Forward events to the projection engine (if available)."""
        engine = getattr(self._app_state, "projection_engine", None) if self._app_state else None
        if engine is None:
            return
        for event in events:
            with contextlib.suppress(Exception):
                await engine.project(event)

    def _build_config(self, run_id: str) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": run_id,
                "run_id": run_id,
                "agent_runtime": self._agent_runtime,
                "app_state": self._app_state,
                "pipeline_store": getattr(self._app_state, "pipeline_store", None),
                "sandbox_manager": getattr(self._app_state, "sandbox_manager", None),
                "credential_store": getattr(self._app_state, "credential_store", None),
                "code_artifact_store": getattr(self._app_state, "code_artifact_store", None),
                "test_result_store": getattr(self._app_state, "test_result_store", None),
            }
        }

    async def execute(self, command: StartWorkflow) -> str:
        run_id = command.run_id or str(uuid4())

        # Publish queued event and acquire semaphore for concurrency control
        self._queue_depth += 1
        position = self._queue_depth
        queued_event = WorkflowQueued(
            event_type="WorkflowQueued",
            payload={
                "run_id": run_id,
                "workflow_id": command.workflow_type,
                "queue_position": position,
            },
        )
        await self._event_store.append(stream_id=f"run:{run_id}", events=[queued_event])
        await self._project_events([queued_event])

        # Update pipeline status to queued while waiting
        await _update_pipeline_status(self._app_state, run_id, "queued")

        try:
            await self._semaphore.acquire()
        except BaseException:
            self._queue_depth -= 1
            raise
        self._queue_depth -= 1

        try:
            return await self._execute_inner(command, run_id)
        finally:
            self._semaphore.release()

    async def _execute_inner(self, command: StartWorkflow, run_id: str) -> str:
        """Inner execution logic, called while holding the semaphore."""
        from lintel.workflows.nodes._runtime_registry import register as _register_runtime

        stream_id = f"run:{run_id}"

        # Register services so nodes can look them up after LangGraph interrupts
        _register_runtime(
            run_id,
            agent_runtime=self._agent_runtime,
            sandbox_manager=getattr(self._app_state, "sandbox_manager", None),
            app_state=self._app_state,
        )

        start_event = PipelineRunStarted(
            event_type="PipelineRunStarted",
            payload={
                "pipeline_id": command.workflow_type,
                "run_id": run_id,
                "trigger_type": "command",
                "thread_ref": str(command.thread_ref),
            },
        )
        await self._event_store.append(stream_id=stream_id, events=[start_event])
        await self._project_events([start_event])

        # Ensure pipeline run exists in store (may not if triggered outside /pipelines)
        await self._ensure_pipeline_run(command, run_id)

        # Mark first stage as running
        await _mark_first_stage_running(self._app_state, run_id)

        # Resolve graph: prefer factory (per workflow type), fall back to static graph
        graph = self._graph
        if self._graph_factory is not None:
            graph = self._graph_factory(command.workflow_type)

        config = self._build_config(run_id)
        initial_input = {
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
            "trigger_context": command.trigger_context,
        }

        # Rehydrate state from previous run if continuing
        if command.continue_from_run_id:
            prev_state = await _rehydrate_from_run(self._app_state, command.continue_from_run_id)
            initial_input.update(prev_state)

        # Store graph and command for potential resumption
        self._suspended_runs[run_id] = {
            "graph": graph,
            "command": command,
            "stream_id": stream_id,
            "total_tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        }

        await self._stream_graph(run_id, graph, initial_input, config)
        return run_id

    async def resume(self, run_id: str) -> None:
        """Resume a workflow that was paused at an approval gate."""
        suspended = self._suspended_runs.get(run_id)
        if suspended is None:
            logger.warning("resume_no_suspended_run", run_id=run_id)
            return

        graph = suspended["graph"]
        config = self._build_config(run_id)

        logger.info("workflow_resuming", run_id=run_id)

        # Pass None as input to resume from the interrupt point
        await self._stream_graph(run_id, graph, None, config)

    async def _resolve_step_timeout(self, run_id: str, node_name: str) -> float:
        """Resolve the effective timeout for a given node in a pipeline run."""
        step_config = None
        pipeline_timeout = None
        global_default = None

        # Look up step configs from the workflow definition via the pipeline run
        if self._app_state is not None:
            pipeline_store = getattr(self._app_state, "pipeline_store", None)
            wf_def_store = getattr(self._app_state, "workflow_definition_store", None)
            if pipeline_store is not None:
                try:
                    run = await pipeline_store.get(run_id)
                    if run is not None and wf_def_store is not None:
                        wf_def = await wf_def_store.get(run.workflow_definition_id)
                        if wf_def is not None:
                            from lintel.workflows.types import StepTimeoutConfig

                            for sc in getattr(wf_def, "step_configs", ()):
                                if sc.node_name == node_name:
                                    step_config = sc
                                    break
                            # Build pipeline-level timeout from step_timeout_seconds
                            # stored on the run or definition
                            agg = getattr(wf_def, "step_timeout_seconds", None)
                            if agg:
                                pipeline_timeout = StepTimeoutConfig(default_seconds=agg)
                except Exception:
                    logger.debug("resolve_step_timeout_lookup_failed", run_id=run_id)

            # Global default from settings
            settings = getattr(self._app_state, "settings", None)
            if settings is not None:
                global_default = getattr(settings, "default_step_timeout_seconds", None)

        return resolve_timeout(
            step_config=step_config,
            pipeline_timeout=pipeline_timeout,
            global_default=global_default,
        )

    @staticmethod
    def _get_current_node(graph: Any, config: dict[str, Any]) -> str:  # noqa: ANN401
        """Query the graph to determine which node is about to execute."""
        try:
            graph_state = graph.get_state(config)
            if graph_state.next:
                return str(graph_state.next[0])
        except Exception:
            pass
        return "unknown"

    async def _handle_step_timeout(
        self,
        stream_id: str,
        run_id: str,
        node_name: str,
        timeout_seconds: float,
    ) -> None:
        """Handle a per-step timeout: mark stage, emit event, update status, notify."""
        logger.warning(
            "step_timed_out",
            run_id=run_id,
            node_name=node_name,
            timeout_seconds=timeout_seconds,
        )
        await _mark_stage_timed_out(self._app_state, run_id, node_name, timeout_seconds)
        await self._emit_timeout_event(stream_id, run_id, node_name, timeout_seconds)
        await _update_pipeline_status(self._app_state, run_id, "failed")
        await _notify_chat(
            self._app_state,
            run_id,
            f"⏱️ **{node_name}** timed out after {timeout_seconds:.0f}s\n"
            f"[View pipeline →](/pipelines/{run_id})",
        )

    async def _emit_timeout_event(
        self,
        stream_id: str,
        run_id: str,
        node_name: str,
        timeout_seconds: float,
    ) -> None:
        """Emit a PipelineStageTimedOut event and project it."""
        timed_out_event = PipelineStageTimedOut(
            event_type="PipelineStageTimedOut",
            payload={
                "run_id": run_id,
                "node_name": node_name,
                "timeout_seconds": timeout_seconds,
            },
        )
        await self._event_store.append(stream_id=stream_id, events=[timed_out_event])
        await self._project_events([timed_out_event])

    async def _stream_graph(
        self,
        run_id: str,
        graph: Any,  # noqa: ANN401
        input_data: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> None:
        """Stream the graph and handle chunks. Detects interrupts."""
        stream_id = f"run:{run_id}"
        suspended = self._suspended_runs.get(run_id, {})
        total_tokens = suspended.get(
            "total_tokens",
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )
        total_tokens["_step_start"] = time.time()

        try:
            # Determine which node is about to run so we can apply its timeout.
            current_node = self._get_current_node(graph, config)
            node_timeout = await self._resolve_step_timeout(run_id, current_node)

            stream = graph.astream(input_data, config=config)
            try:
                async_iter = stream.__aiter__()
                while True:
                    try:
                        async with asyncio.timeout(node_timeout):
                            chunk = await async_iter.__anext__()
                    except StopAsyncIteration:
                        break
                    except TimeoutError:
                        await self._handle_step_timeout(
                            stream_id, run_id, current_node, node_timeout
                        )
                        return

                    for node_name, output in chunk.items():
                        if node_name == "__end__":
                            continue
                        phase = (
                            output.get("current_phase", node_name)
                            if isinstance(output, dict)
                            else node_name
                        )
                        timestamp_ms = int(time.time() * 1000)

                        # Record step metrics
                        step_start = total_tokens.get("_step_start", time.time())
                        duration = time.time() - step_start
                        if self._step_metrics is not None:
                            self._step_metrics.record_step_duration(
                                run_id,
                                node_name,
                                node_name,
                                "completed",
                                duration,
                            )
                        if isinstance(output, dict):
                            for entry in output.get("token_usage", []):
                                if isinstance(entry, dict):
                                    step_total = entry.get("total_tokens", 0)
                                    model_id = entry.get("model", "unknown")
                                    if step_total and self._step_metrics is not None:
                                        self._step_metrics.record_step_tokens(
                                            run_id,
                                            node_name,
                                            model_id,
                                            step_total,
                                        )
                        total_tokens["_step_start"] = time.time()

                        stage_event = PipelineStageCompleted(
                            event_type="PipelineStageCompleted",
                            payload={
                                "run_id": run_id,
                                "node_name": node_name,
                                "output": output,
                                "timestamp_ms": timestamp_ms,
                            },
                        )
                        await self._event_store.append(stream_id=stream_id, events=[stage_event])
                        await self._project_events([stage_event])
                        await _mark_stage_completed(
                            self._app_state, run_id, node_name, timestamp_ms
                        )

                        # Accumulate token usage from node output
                        if isinstance(output, dict):
                            for entry in output.get("token_usage", []):
                                if isinstance(entry, dict):
                                    total_tokens["input_tokens"] += entry.get("input_tokens", 0)
                                    total_tokens["output_tokens"] += entry.get("output_tokens", 0)
                                    total_tokens["total_tokens"] += entry.get("total_tokens", 0)

                        # Chat notifications
                        await _send_stage_notification(self._app_state, run_id, node_name, output)

                        if self._on_stage_complete is not None:
                            with contextlib.suppress(Exception):
                                await self._on_stage_complete(node_name, phase)

                    # Resolve timeout for the next node before awaiting the next chunk.
                    current_node = self._get_current_node(graph, config)
                    node_timeout = await self._resolve_step_timeout(run_id, current_node)
            finally:
                # Ensure the async generator is properly closed to avoid
                # "coroutine was never awaited" warnings.
                with contextlib.suppress(Exception):
                    await stream.aclose()

            # Check if graph is interrupted (has pending next nodes)
            graph_state = graph.get_state(config)
            if graph_state.next:
                # Graph paused at an interrupt_before node
                next_node = graph_state.next[0]
                logger.info(
                    "workflow_interrupted",
                    run_id=run_id,
                    next_node=next_node,
                )

                # Evaluate policy for this gate
                policy_action = await _evaluate_policy(self._app_state, run_id, next_node)

                if policy_action == "auto_approve":
                    logger.info(
                        "policy_auto_approve",
                        run_id=run_id,
                        node=next_node,
                    )
                    await _notify_chat(
                        self._app_state,
                        run_id,
                        f"✅ **{next_node}** — auto-approved by policy\n"
                        f"[View pipeline →](/pipelines/{run_id})",
                    )
                    # Resume immediately — pass None to continue from interrupt
                    await self._stream_graph(run_id, graph, None, config)
                    return

                if policy_action == "block":
                    logger.info(
                        "policy_blocked",
                        run_id=run_id,
                        node=next_node,
                    )
                    await _mark_running_stages_failed(self._app_state, run_id, "Blocked by policy")
                    await _update_pipeline_status(self._app_state, run_id, "failed")
                    await _notify_chat(
                        self._app_state,
                        run_id,
                        f"🚫 **{next_node}** — blocked by policy\n"
                        f"[View pipeline →](/pipelines/{run_id})",
                    )
                    return

                if policy_action == "notify":
                    await _notify_chat(
                        self._app_state,
                        run_id,
                        f"📢 **{next_node}** — policy notification: gate reached\n"
                        f"[View pipeline →](/pipelines/{run_id})",
                    )

                # Default: require_approval
                await _mark_stage_waiting_approval(self._app_state, run_id, next_node)
                await _update_pipeline_status(self._app_state, run_id, "waiting_approval")
                await _create_approval_request(self._app_state, run_id, next_node)
                await _notify_chat(
                    self._app_state,
                    run_id,
                    f"⏸️ **{next_node}** — waiting for approval\n"
                    f"[View pipeline →](/pipelines/{run_id})",
                )
                return

            # Graph completed normally
            from lintel.workflows.nodes._runtime_registry import unregister as _unregister_runtime

            self._suspended_runs.pop(run_id, None)
            _unregister_runtime(run_id)

            # Determine final status — if any stage failed/skipped due to
            # failure, the pipeline should be marked failed, not succeeded.
            final_status = await _determine_final_status(self._app_state, run_id)

            completed_event = PipelineRunCompleted(
                event_type="PipelineRunCompleted",
                payload={
                    "run_id": run_id,
                    "status": final_status,
                    "token_usage": total_tokens,
                },
            )
            await self._event_store.append(stream_id=stream_id, events=[completed_event])
            await self._project_events([completed_event])
            await _update_pipeline_status(self._app_state, run_id, final_status)
            command = suspended.get("command")
            if command:
                if final_status == "failed":
                    await _fail_work_item(
                        self._app_state,
                        self._event_store,
                        self._project_events,
                        run_id,
                        command.work_item_id or "",
                        command.project_id or "",
                    )
                else:
                    await _complete_work_item(
                        self._app_state,
                        self._event_store,
                        self._project_events,
                        command.work_item_id or "",
                    )
            token_summary = ""
            if total_tokens["total_tokens"] > 0:
                token_summary = (
                    f"\n📊 Tokens: {total_tokens['total_tokens']:,} "
                    f"({total_tokens['input_tokens']:,} in / "
                    f"{total_tokens['output_tokens']:,} out)"
                )
            if final_status == "failed":
                await _notify_chat(
                    self._app_state,
                    run_id,
                    f"❌ **Workflow completed with failures**{token_summary}\n"
                    f"[View pipeline →](/pipelines/{run_id})",
                )
            else:
                await _notify_chat(
                    self._app_state,
                    run_id,
                    f"🎉 **Workflow completed successfully**{token_summary}\n"
                    f"[View pipeline →](/pipelines/{run_id})",
                )
        except TimeoutError:
            # Aggregate pipeline timeout exceeded
            self._suspended_runs.pop(run_id, None)
            last_node = "unknown"
            elapsed = time.time() - total_tokens.get("_step_start", time.time())
            await _mark_running_stages_failed(self._app_state, run_id, "Pipeline timed out")
            await self._emit_timeout_event(stream_id, run_id, last_node, elapsed)
            await _update_pipeline_status(self._app_state, run_id, "failed")
            await _notify_chat(
                self._app_state,
                run_id,
                f"⏱️ **Pipeline timed out** after {elapsed:.0f}s\n"
                f"[View pipeline →](/pipelines/{run_id})",
            )
        except Exception as exc:
            self._suspended_runs.pop(run_id, None)
            await _mark_running_stages_failed(self._app_state, run_id, str(exc))
            failed_event = PipelineRunFailed(
                event_type="PipelineRunFailed",
                payload={"run_id": run_id, "error": str(exc)},
            )
            await self._event_store.append(stream_id=stream_id, events=[failed_event])
            await self._project_events([failed_event])
            await _update_pipeline_status(self._app_state, run_id, "failed")
            command = suspended.get("command")
            if command:
                await _fail_work_item(
                    self._app_state,
                    self._event_store,
                    self._project_events,
                    run_id,
                    command.work_item_id or "",
                    command.project_id or "",
                )
            await _notify_chat(
                self._app_state,
                run_id,
                f"❌ **Workflow failed**: {exc}\n[View pipeline →](/pipelines/{run_id})",
            )

    # ---------------------------------------------------------------------------
    # Compatibility shims — thin wrappers so existing call-sites using self.* work
    # ---------------------------------------------------------------------------

    async def append_log(self, run_id: str, stage_name: str, message: str) -> None:
        """Append a log line to a stage (delegated to stage tracking)."""
        from lintel.workflows.nodes._stage_tracking import StageTracker

        class _FakeState(dict):  # type: ignore[type-arg]
            pass

        fake_config = {"configurable": self._build_config(run_id)["configurable"]}

        tracker = StageTracker(fake_config, _FakeState())
        with contextlib.suppress(Exception):
            await tracker.append_log(stage_name, message)

    async def _get_stage_id(self, run_id: str, node_name: str) -> str | None:
        return await _get_stage_id(self._app_state, run_id, node_name)

    async def _mark_stage_completed(self, run_id: str, node_name: str, timestamp_ms: int) -> None:
        await _mark_stage_completed(self._app_state, run_id, node_name, timestamp_ms)

    async def _send_stage_notification(
        self,
        run_id: str,
        node_name: str,
        output: Any,  # noqa: ANN401
    ) -> None:
        await _send_stage_notification(self._app_state, run_id, node_name, output)

    async def _notify_chat(self, run_id: str, message: str) -> None:
        await _notify_chat(self._app_state, run_id, message)

    async def _update_pipeline_status(self, run_id: str, status: str) -> None:
        await _update_pipeline_status(self._app_state, run_id, status)

    async def _determine_final_status(self, run_id: str) -> str:
        return await _determine_final_status(self._app_state, run_id)

    async def _ensure_pipeline_run(self, command: StartWorkflow, run_id: str) -> None:
        """Create a PipelineRun in the store if one doesn't already exist."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        existing = await pipeline_store.get(run_id)
        if existing is not None:
            return
        try:
            from datetime import UTC, datetime

            from lintel.pipelines_api._helpers import _stage_names_for_workflow
            from lintel.workflows.types import PipelineRun, Stage

            stage_names = _stage_names_for_workflow(command.workflow_type)
            stages = tuple(
                Stage(stage_id=str(uuid4()), name=name, stage_type=name) for name in stage_names
            )
            run = PipelineRun(
                run_id=run_id,
                project_id=command.project_id,
                work_item_id=command.work_item_id,
                workflow_definition_id=command.workflow_type,
                trigger_type="workflow",
                trigger_context=command.trigger_context,
                stages=stages,
                created_at=datetime.now(UTC).isoformat(),
            )
            await pipeline_store.add(run)
            logger.info("pipeline_run_auto_created: %s", run_id)
        except Exception:
            logger.warning("pipeline_run_auto_create_failed: %s", run_id, exc_info=True)

    async def _mark_first_stage_running(self, run_id: str) -> None:
        await _mark_first_stage_running(self._app_state, run_id)

    async def _mark_running_stages_failed(self, run_id: str, error: str) -> None:
        await _mark_running_stages_failed(self._app_state, run_id, error)

    async def _mark_stage_waiting_approval(self, run_id: str, node_name: str) -> None:
        await _mark_stage_waiting_approval(self._app_state, run_id, node_name)

    async def _evaluate_policy(self, run_id: str, node_name: str) -> str:
        return await _evaluate_policy(self._app_state, run_id, node_name)

    async def _create_approval_request(self, run_id: str, node_name: str) -> None:
        await _create_approval_request(self._app_state, run_id, node_name)

    async def _is_auto_move_enabled(self, project_id: str) -> bool:
        from lintel.workflows._executor_artifacts import is_auto_move_enabled

        return await is_auto_move_enabled(self._app_state, project_id)

    async def _fail_work_item(self, command: StartWorkflow) -> None:
        await _fail_work_item(
            self._app_state,
            self._event_store,
            self._project_events,
            "",
            command.work_item_id or "",
            command.project_id or "",
        )

    async def _complete_work_item(self, command: StartWorkflow) -> None:
        await _complete_work_item(
            self._app_state,
            self._event_store,
            self._project_events,
            command.work_item_id or "",
        )

    async def _auto_promote_if_capacity(
        self, project_id: str, work_item_store: object, *, exclude_id: str = ""
    ) -> None:
        await _auto_promote_if_capacity(
            self._app_state,
            self._event_store,
            self._project_events,
            project_id,
            work_item_store,
            exclude_id=exclude_id,
        )

    async def _rehydrate_from_run(self, prev_run_id: str) -> dict[str, Any]:
        return await _rehydrate_from_run(self._app_state, prev_run_id)
