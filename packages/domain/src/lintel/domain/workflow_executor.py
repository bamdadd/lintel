"""WorkflowExecutor — wires StartWorkflow commands to LangGraph execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import contextlib
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.contracts.events import (
    PipelineRunCompleted,
    PipelineRunFailed,
    PipelineRunStarted,
    PipelineStageCompleted,
    WorkItemCompleted,
    WorkItemUpdated,
)

if TYPE_CHECKING:
    from lintel.contracts.commands import StartWorkflow
    from lintel.contracts.protocols import EventStore, StepMetricsRecorder
    from lintel.contracts.types import Stage

logger = structlog.get_logger()


def _dict_to_stage(d: dict[str, Any]) -> Stage:
    """Convert a plain dict to a Stage dataclass instance."""
    from dataclasses import fields as dc_fields

    from lintel.contracts.types import Stage, StageStatus

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
        from lintel.workflows.nodes._runtime_registry import register as _register_runtime

        run_id = command.run_id or str(uuid4())
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

        # Mark first stage as running
        await self._mark_first_stage_running(run_id)

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
        }

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
            async for chunk in graph.astream(input_data, config=config):
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
                    await self._mark_stage_completed(run_id, node_name, timestamp_ms)

                    # Accumulate token usage from node output
                    if isinstance(output, dict):
                        for entry in output.get("token_usage", []):
                            if isinstance(entry, dict):
                                total_tokens["input_tokens"] += entry.get("input_tokens", 0)
                                total_tokens["output_tokens"] += entry.get("output_tokens", 0)
                                total_tokens["total_tokens"] += entry.get("total_tokens", 0)

                    # Chat notifications
                    await self._send_stage_notification(run_id, node_name, output)

                    if self._on_stage_complete is not None:
                        with contextlib.suppress(Exception):
                            await self._on_stage_complete(node_name, phase)

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
                policy_action = await self._evaluate_policy(run_id, next_node)

                if policy_action == "auto_approve":
                    logger.info(
                        "policy_auto_approve",
                        run_id=run_id,
                        node=next_node,
                    )
                    await self._notify_chat(
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
                    await self._mark_running_stages_failed(run_id, "Blocked by policy")
                    await self._update_pipeline_status(run_id, "failed")
                    await self._notify_chat(
                        run_id,
                        f"🚫 **{next_node}** — blocked by policy\n"
                        f"[View pipeline →](/pipelines/{run_id})",
                    )
                    return

                if policy_action == "notify":
                    await self._notify_chat(
                        run_id,
                        f"📢 **{next_node}** — policy notification: gate reached\n"
                        f"[View pipeline →](/pipelines/{run_id})",
                    )

                # Default: require_approval
                await self._mark_stage_waiting_approval(run_id, next_node)
                await self._update_pipeline_status(run_id, "waiting_approval")
                await self._create_approval_request(run_id, next_node)
                await self._notify_chat(
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
            final_status = await self._determine_final_status(run_id)

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
            await self._update_pipeline_status(run_id, final_status)
            command = suspended.get("command")
            if command:
                if final_status == "failed":
                    await self._fail_work_item(command)
                else:
                    await self._complete_work_item(command)
            token_summary = ""
            if total_tokens["total_tokens"] > 0:
                token_summary = (
                    f"\n📊 Tokens: {total_tokens['total_tokens']:,} "
                    f"({total_tokens['input_tokens']:,} in / "
                    f"{total_tokens['output_tokens']:,} out)"
                )
            if final_status == "failed":
                await self._notify_chat(
                    run_id,
                    f"❌ **Workflow completed with failures**{token_summary}\n"
                    f"[View pipeline →](/pipelines/{run_id})",
                )
            else:
                await self._notify_chat(
                    run_id,
                    f"🎉 **Workflow completed successfully**{token_summary}\n"
                    f"[View pipeline →](/pipelines/{run_id})",
                )
        except Exception as exc:
            self._suspended_runs.pop(run_id, None)
            await self._mark_running_stages_failed(run_id, str(exc))
            failed_event = PipelineRunFailed(
                event_type="PipelineRunFailed",
                payload={"run_id": run_id, "error": str(exc)},
            )
            await self._event_store.append(stream_id=stream_id, events=[failed_event])
            await self._project_events([failed_event])
            await self._update_pipeline_status(run_id, "failed")
            command = suspended.get("command")
            if command:
                await self._fail_work_item(command)
            await self._notify_chat(
                run_id,
                f"❌ **Workflow failed**: {exc}\n[View pipeline →](/pipelines/{run_id})",
            )

    async def _send_stage_notification(
        self,
        run_id: str,
        node_name: str,
        output: Any,  # noqa: ANN401
    ) -> None:
        """Send a chat notification for a completed stage."""
        is_approval = "approve" in node_name or "approval" in node_name
        if is_approval:
            await self._notify_chat(
                run_id,
                f"✅ **{node_name}** — approved\n[View pipeline →](/pipelines/{run_id})",
            )
        elif node_name == "setup_workspace" and isinstance(output, dict):
            sandbox_id = output.get("sandbox_id", "")
            feature_branch = output.get("feature_branch", "")
            lines = ["✅ **setup_workspace** completed\n"]
            if sandbox_id:
                lines.append(f"**Sandbox:** [{sandbox_id[:12]}](/sandboxes/{sandbox_id})")
            if feature_branch:
                lines.append(f"**Branch:** `{feature_branch}`")
            await self._notify_chat(run_id, "\n".join(lines))
        elif node_name == "research" and isinstance(output, dict):
            ctx = output.get("research_context", "")
            if ctx:
                lines = ["✅ **research** completed\n"]
                lines.append("---\n")
                # Include the research report (truncate if very long)
                report = ctx if len(ctx) <= 4000 else ctx[:4000] + "\n\n…(truncated)"
                lines.append(report)
                await self._notify_chat(run_id, "\n".join(lines))
            else:
                await self._notify_chat(run_id, f"✅ **{node_name}** completed")
        elif node_name == "plan" and isinstance(output, dict):
            plan = output.get("plan", {})
            if isinstance(plan, dict) and plan.get("tasks"):
                lines = ["✅ **plan** completed\n"]
                summary = plan.get("summary", "")
                if summary:
                    lines.append(f"**Summary:** {summary}\n")
                lines.append("**Tasks:**")
                for i, task in enumerate(plan.get("tasks", []), 1):
                    if isinstance(task, dict):
                        title = task.get("title", "")
                        desc = task.get("description", "")
                        complexity = task.get("complexity", "")
                        suffix = f" [{complexity}]" if complexity else ""
                        lines.append(f"  {i}. **{title}**{suffix}")
                        if desc:
                            lines.append(f"     {desc}")
                    else:
                        lines.append(f"  {i}. {task}")
                await self._notify_chat(run_id, "\n".join(lines))
            else:
                await self._notify_chat(run_id, f"✅ **{node_name}** completed")
        elif node_name == "implement" and isinstance(output, dict):
            lines = ["✅ **implement** completed\n"]
            # Show agent output summary
            for entry in output.get("agent_outputs", []):
                if isinstance(entry, dict):
                    node = entry.get("node", "")
                    if node == "implement":
                        impl_output = entry.get("output", "")
                        if impl_output:
                            # Truncate long output
                            text = (
                                impl_output
                                if len(impl_output) <= 4000
                                else impl_output[:4000] + "\n\n…(truncated)"
                            )
                            lines.append("**Changes:**\n")
                            lines.append(text)
                    elif node == "test":
                        verdict = entry.get("verdict", "")
                        if verdict:
                            icon = "✅" if verdict == "passed" else "❌"
                            lines.append(f"\n**Tests:** {icon} {verdict}")
            # Show diff stats if available
            for artifact in output.get("sandbox_results", []):
                if isinstance(artifact, dict):
                    diff = artifact.get("content", "")
                    if diff:
                        diff_lines = diff.strip().split("\n")
                        files_changed = sum(1 for ln in diff_lines if ln.startswith("diff --git"))
                        additions = sum(
                            1
                            for ln in diff_lines
                            if ln.startswith("+") and not ln.startswith("+++")
                        )
                        deletions = sum(
                            1
                            for ln in diff_lines
                            if ln.startswith("-") and not ln.startswith("---")
                        )
                        lines.append(
                            f"\n**Diff:** {files_changed} files changed, +{additions} -{deletions}"
                        )
            await self._notify_chat(run_id, "\n".join(lines))
        else:
            await self._notify_chat(run_id, f"✅ **{node_name}** completed")

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

    async def _get_stage_id(self, run_id: str, node_name: str) -> str | None:
        """Look up the stage_id for a given node name."""
        if self._app_state is None:
            return None
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return None
        try:
            from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

            stage_name = NODE_TO_STAGE.get(node_name, node_name)
            run = await pipeline_store.get(run_id)
            if run is None:
                return None
            for stage in run.stages:
                if isinstance(stage, dict):
                    stage = _dict_to_stage(stage)
                if stage.name == stage_name:
                    return str(stage.stage_id)
        except Exception:
            pass
        return None

    async def _evaluate_policy(self, run_id: str, node_name: str) -> str:
        """Evaluate policy for an approval gate. Returns action string."""
        if self._app_state is None:
            return "require_approval"
        try:
            from lintel.workflows.nodes._policy import evaluate_gate_policy
            from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

            policy_store = getattr(self._app_state, "policy_store", None)
            pipeline_store = getattr(self._app_state, "pipeline_store", None)

            # Get project_id from pipeline run
            project_id = ""
            if pipeline_store is not None:
                run = await pipeline_store.get(run_id)
                if run is not None:
                    project_id = getattr(run, "project_id", "") or ""

            gate_type = NODE_TO_STAGE.get(node_name, node_name)
            action = await evaluate_gate_policy(policy_store, project_id, gate_type)
            result = action.value if hasattr(action, "value") else str(action)
            logger.info(
                "policy_evaluated",
                run_id=run_id,
                gate_type=gate_type,
                action=result,
            )
            return result
        except Exception as exc:
            logger.warning(
                "policy_evaluation_failed",
                run_id=run_id,
                error=str(exc),
            )
            return "require_approval"

    async def _create_approval_request(self, run_id: str, node_name: str) -> None:
        """Create an ApprovalRequest record when workflow pauses at an approval gate."""
        if self._app_state is None:
            return
        approval_store = getattr(self._app_state, "approval_request_store", None)
        if approval_store is None:
            return
        try:
            from lintel.contracts.types import ApprovalRequest
            from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

            gate_type = NODE_TO_STAGE.get(node_name, node_name)
            approval = ApprovalRequest(
                approval_id=str(uuid4()),
                run_id=run_id,
                gate_type=gate_type,
            )
            await approval_store.add(approval)
            logger.info(
                "approval_request_created",
                approval_id=approval.approval_id,
                run_id=run_id,
                gate_type=gate_type,
            )
        except Exception as exc:
            logger.warning(
                "create_approval_request_failed",
                run_id=run_id,
                node_name=node_name,
                error=str(exc),
            )

    async def _mark_stage_waiting_approval(self, run_id: str, node_name: str) -> None:
        """Mark an approval gate stage as waiting_approval."""
        if self._app_state is None:
            return
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return
        try:
            from dataclasses import replace
            from datetime import UTC, datetime

            from lintel.contracts.types import StageStatus
            from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

            stage_name = NODE_TO_STAGE.get(node_name, node_name)
            run = await pipeline_store.get(run_id)
            if run is None:
                return

            now = datetime.now(UTC).isoformat()
            updated_stages = []
            for stage in run.stages:
                if isinstance(stage, dict):
                    stage = _dict_to_stage(stage)
                if stage.name == stage_name:
                    updated_stages.append(
                        replace(
                            stage,
                            status=StageStatus.WAITING_APPROVAL,
                            started_at=now,
                        )
                    )
                else:
                    updated_stages.append(stage)
            updated = replace(run, stages=tuple(updated_stages))
            await pipeline_store.update(updated)
        except Exception as exc:
            logger.warning(
                "mark_stage_waiting_approval_failed",
                run_id=run_id,
                node_name=node_name,
                error=str(exc),
            )

    async def _mark_stage_completed(
        self,
        run_id: str,
        node_name: str,
        timestamp_ms: int,
    ) -> None:
        """Mark a pipeline stage as completed in the store."""
        # Resolve graph node name to pipeline stage name
        from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

        node_name = NODE_TO_STAGE.get(node_name, node_name)
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
                    # Preserve status if the node already marked itself failed/skipped
                    final_status = (
                        stage.status
                        if stage.status in (StageStatus.FAILED, StageStatus.SKIPPED)
                        else StageStatus.SUCCEEDED
                    )
                    updated_stages.append(
                        replace(
                            stage,
                            status=final_status,
                            started_at=started,
                            finished_at=finished,
                            duration_ms=duration,
                        )
                    )
                    found = True
                else:
                    updated_stages.append(stage)
            # Mark the next stage as running (only if current stage succeeded)
            if found and final_status == StageStatus.SUCCEEDED:
                for i, s in enumerate(updated_stages):
                    if isinstance(s, dict):
                        s = _dict_to_stage(s)
                    if s.status == StageStatus.SUCCEEDED:
                        continue
                    if s.status == StageStatus.PENDING:
                        updated_stages[i] = replace(
                            s, status=StageStatus.RUNNING, started_at=finished
                        )
                        break
            updated = replace(run, stages=tuple(updated_stages))
            await pipeline_store.update(updated)
        except Exception as exc:
            logger.warning(
                "mark_stage_completed_failed", run_id=run_id, node_name=node_name, error=str(exc)
            )

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
            logger.warning(
                "update_pipeline_status_failed", run_id=run_id, status=status, error=str(exc)
            )

    async def _determine_final_status(self, run_id: str) -> str:
        """Check pipeline stages to determine if the run succeeded or failed.

        If any stage has a failed or skipped status, the pipeline is considered
        failed — even though the graph itself completed without raising.
        """
        if self._app_state is None:
            return "succeeded"
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return "succeeded"
        try:
            run = await pipeline_store.get(run_id)
            if run is None:
                return "succeeded"
            from lintel.contracts.types import StageStatus

            for stage in run.stages:
                s = stage
                if isinstance(s, dict):
                    from lintel.contracts.types import Stage

                    s = Stage(**s)
                if s.status in (StageStatus.FAILED,):
                    return "failed"
        except Exception:
            logger.warning("determine_final_status_failed", run_id=run_id)
        return "succeeded"

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
            logger.warning("mark_first_stage_running_failed", run_id=run_id, error=str(exc))

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
                elif stage.status == StageStatus.PENDING:
                    updated_stages.append(replace(stage, status=StageStatus.SKIPPED))
                    changed = True
                else:
                    updated_stages.append(stage)
            if changed:
                updated = replace(run, stages=tuple(updated_stages))
                await pipeline_store.update(updated)
        except Exception as exc:
            logger.warning(
                "mark_running_stages_failed_error",
                run_id=run_id,
                error=str(exc),
            )

    async def _is_auto_move_enabled(self, project_id: str) -> bool:
        """Check if any board for this project has auto_move enabled."""
        if self._app_state is None:
            return False
        board_store = getattr(self._app_state, "board_store", None)
        if board_store is None:
            return False
        try:
            boards = await board_store.list_by_project(project_id)
            return any(
                (
                    b.get("auto_move", False)
                    if isinstance(b, dict)
                    else getattr(b, "auto_move", False)
                )
                for b in boards
            )
        except Exception:
            return False

    async def _fail_work_item(self, command: StartWorkflow) -> None:
        """Mark the work item as failed (or open if auto_move is on)."""
        if self._app_state is None:
            return
        work_item_store = getattr(self._app_state, "work_item_store", None)
        if work_item_store is None or not command.work_item_id:
            return
        try:
            item = await work_item_store.get(command.work_item_id)
            if item is None:
                return
            project_id = item.get("project_id", "")
            auto_move = await self._is_auto_move_enabled(project_id)
            new_status = "open" if auto_move else "failed"
            item["status"] = new_status
            await work_item_store.update(command.work_item_id, item)
            # Emit audit event for work item failure
            stream_id = f"work_item:{command.work_item_id}"
            event = WorkItemUpdated(
                event_type="WorkItemUpdated",
                payload={
                    "work_item_id": command.work_item_id,
                    "status": new_status,
                    "auto_moved": auto_move,
                },
            )
            await self._event_store.append(stream_id=stream_id, events=[event])
            await self._project_events([event])
            if auto_move:
                logger.info(
                    "auto_move_failed_to_todo",
                    work_item_id=command.work_item_id,
                )
                # Item moved from in_progress to open — WIP capacity freed
                # Exclude the just-failed item from promotion
                await self._auto_promote_if_capacity(
                    project_id,
                    work_item_store,
                    exclude_id=command.work_item_id,
                )
        except Exception as exc:
            logger.warning(
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
            # Emit audit event for work item completion
            stream_id = f"work_item:{command.work_item_id}"
            event = WorkItemCompleted(
                event_type="WorkItemCompleted",
                payload={
                    "work_item_id": command.work_item_id,
                    "status": "closed",
                },
            )
            await self._event_store.append(stream_id=stream_id, events=[event])
            await self._project_events([event])
            # Auto-promote: if auto_move is on and WIP has capacity, move oldest open item
            project_id = item.get("project_id", "")
            await self._auto_promote_if_capacity(project_id, work_item_store)
        except Exception as exc:
            logger.warning(
                "complete_work_item_failed", work_item_id=command.work_item_id, error=str(exc)
            )

    async def _auto_promote_if_capacity(
        self, project_id: str, work_item_store: object, *, exclude_id: str = ""
    ) -> None:
        """Promote the oldest open work item to in_progress if WIP has capacity."""
        if not project_id or self._app_state is None:
            return
        if not await self._is_auto_move_enabled(project_id):
            return
        board_store = getattr(self._app_state, "board_store", None)
        if board_store is None:
            return
        try:
            boards = await board_store.list_by_project(project_id)
            # Find the in_progress WIP limit
            wip_limit = 0
            for board in boards:
                columns = (
                    board.get("columns", [])
                    if isinstance(board, dict)
                    else getattr(board, "columns", ())
                )
                for col in columns:
                    col_status = (
                        col.get("work_item_status", "")
                        if isinstance(col, dict)
                        else getattr(col, "work_item_status", "")
                    )
                    if col_status == "in_progress":
                        wip_limit = int(
                            col.get("wip_limit", 0)
                            if isinstance(col, dict)
                            else getattr(col, "wip_limit", 0)
                        )
                        break

            all_items = await work_item_store.list_all(project_id=project_id)  # type: ignore[attr-defined]
            in_progress_count = sum(1 for i in all_items if i.get("status") == "in_progress")
            # If no WIP limit or under capacity, promote oldest open item
            if wip_limit == 0 or in_progress_count < wip_limit:
                open_items = [
                    i
                    for i in all_items
                    if i.get("status") == "open" and i.get("work_item_id") != exclude_id
                ]
                if not open_items:
                    return
                # Pick the item at the top of the board column (lowest position)
                open_items.sort(key=lambda i: i.get("column_position", 0))
                candidate = open_items[0]
                candidate_id = candidate.get("work_item_id", "")
                if not candidate_id:
                    return
                candidate["status"] = "in_progress"
                await work_item_store.update(candidate_id, candidate)  # type: ignore[attr-defined]
                logger.info(
                    "auto_promote_to_in_progress",
                    work_item_id=candidate_id,
                    project_id=project_id,
                )
                # Emit event
                stream_id = f"work_item:{candidate_id}"
                event = WorkItemUpdated(
                    event_type="WorkItemUpdated",
                    payload={
                        "work_item_id": candidate_id,
                        "status": "in_progress",
                        "auto_promoted": True,
                    },
                )
                await self._event_store.append(stream_id=stream_id, events=[event])
                await self._project_events([event])
        except Exception as exc:
            logger.warning(
                "auto_promote_failed",
                project_id=project_id,
                error=str(exc),
            )
