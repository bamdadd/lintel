"""Stage lifecycle helpers extracted from WorkflowExecutor."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.protocols import EventStore

logger = structlog.get_logger()


def _dict_to_stage_local(d: dict[str, Any]) -> Any:
    """Convert a plain dict to a Stage dataclass instance (local import to avoid circular)."""
    from dataclasses import fields as dc_fields

    from lintel.workflows.types import Stage, StageStatus

    valid = {f.name for f in dc_fields(Stage)}
    filtered = {k: v for k, v in d.items() if k in valid}
    if "status" in filtered and isinstance(filtered["status"], str):
        with contextlib.suppress(ValueError):
            filtered["status"] = StageStatus(filtered["status"])
    return Stage(**filtered)


async def notify_chat(app_state: Any, run_id: str, message: str) -> None:
    """Post a status message to the chat conversation linked to this pipeline."""
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    chat_store = getattr(app_state, "chat_store", None)
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


async def send_stage_notification(
    app_state: Any,
    run_id: str,
    node_name: str,
    output: Any,  # noqa: ANN401
) -> None:
    """Send a chat notification for a completed stage."""
    is_approval = "approve" in node_name or "approval" in node_name
    if is_approval:
        await notify_chat(
            app_state,
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
        await notify_chat(app_state, run_id, "\n".join(lines))
    elif node_name == "research" and isinstance(output, dict):
        ctx = output.get("research_context", "")
        if ctx:
            lines = ["✅ **research** completed\n"]
            lines.append("---\n")
            # Include the research report (truncate if very long)
            report = ctx if len(ctx) <= 4000 else ctx[:4000] + "\n\n…(truncated)"
            lines.append(report)
            await notify_chat(app_state, run_id, "\n".join(lines))
        else:
            await notify_chat(app_state, run_id, f"✅ **{node_name}** completed")
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
            await notify_chat(app_state, run_id, "\n".join(lines))
        else:
            await notify_chat(app_state, run_id, f"✅ **{node_name}** completed")
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
        await notify_chat(app_state, run_id, "\n".join(lines))
    else:
        await notify_chat(app_state, run_id, f"✅ **{node_name}** completed")


async def get_stage_id(app_state: Any, run_id: str, node_name: str) -> str | None:
    """Look up the stage_id for a given node name."""
    if app_state is None:
        return None
    pipeline_store = getattr(app_state, "pipeline_store", None)
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
                stage = _dict_to_stage_local(stage)
            if stage.name == stage_name:
                return str(stage.stage_id)
    except Exception:
        pass
    return None


async def mark_stage_completed(
    app_state: Any,
    run_id: str,
    node_name: str,
    timestamp_ms: int,
) -> None:
    """Mark a pipeline stage as completed in the store."""
    from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

    node_name = NODE_TO_STAGE.get(node_name, node_name)
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return
    try:
        from dataclasses import replace
        from datetime import UTC, datetime

        from lintel.workflows.types import StageStatus

        run = await pipeline_store.get(run_id)
        if run is None:
            return
        finished = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()
        updated_stages = []
        found = False
        final_status = StageStatus.SUCCEEDED
        for stage in run.stages:
            # Handle both Stage dataclass instances and plain dicts (Postgres)
            if isinstance(stage, dict):
                stage = _dict_to_stage_local(stage)
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
                    s = _dict_to_stage_local(s)
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


async def update_pipeline_status(app_state: Any, run_id: str, status: str) -> None:
    """Update the pipeline run status in the pipeline store."""
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return
    try:
        from dataclasses import replace

        run = await pipeline_store.get(run_id)
        if run is not None:
            from lintel.workflows.types import PipelineStatus

            new_status = PipelineStatus(status)
            updated = replace(run, status=new_status)
            await pipeline_store.update(updated)
    except Exception as exc:
        logger.warning(
            "update_pipeline_status_failed", run_id=run_id, status=status, error=str(exc)
        )


async def determine_final_status(app_state: Any, run_id: str) -> str:
    """Check pipeline stages to determine if the run succeeded or failed.

    If any stage has a failed or skipped status, the pipeline is considered
    failed — even though the graph itself completed without raising.
    """
    if app_state is None:
        return "succeeded"
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return "succeeded"
    try:
        run = await pipeline_store.get(run_id)
        if run is None:
            return "succeeded"
        from lintel.workflows.types import StageStatus

        for stage in run.stages:
            s = stage
            if isinstance(s, dict):
                from lintel.workflows.types import Stage

                s = Stage(**s)
            if s.status in (StageStatus.FAILED,):
                return "failed"
    except Exception:
        logger.warning("determine_final_status_failed", run_id=run_id)
    return "succeeded"


async def mark_first_stage_running(app_state: Any, run_id: str) -> None:
    """Mark the first pipeline stage as running."""
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return
    try:
        from dataclasses import replace
        from datetime import UTC, datetime

        from lintel.workflows.types import StageStatus

        run = await pipeline_store.get(run_id)
        if run is None or not run.stages:
            return
        stages = list(run.stages)
        first = stages[0]
        if isinstance(first, dict):
            first = _dict_to_stage_local(first)
        now = datetime.now(UTC).isoformat()
        stages[0] = replace(first, status=StageStatus.RUNNING, started_at=now)
        updated = replace(run, stages=tuple(stages))
        await pipeline_store.update(updated)
    except Exception as exc:
        logger.warning("mark_first_stage_running_failed", run_id=run_id, error=str(exc))


async def mark_running_stages_failed(app_state: Any, run_id: str, error: str) -> None:
    """Mark any stages still in 'running' status as failed when the workflow errors."""
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return
    try:
        from dataclasses import replace

        from lintel.workflows.types import StageStatus

        run = await pipeline_store.get(run_id)
        if run is None:
            return
        updated_stages = []
        changed = False
        for stage in run.stages:
            if isinstance(stage, dict):
                stage = _dict_to_stage_local(stage)
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


async def mark_stage_waiting_approval(app_state: Any, run_id: str, node_name: str) -> None:
    """Mark an approval gate stage as waiting_approval."""
    if app_state is None:
        return
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return
    try:
        from dataclasses import replace
        from datetime import UTC, datetime

        from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE
        from lintel.workflows.types import StageStatus

        stage_name = NODE_TO_STAGE.get(node_name, node_name)
        run = await pipeline_store.get(run_id)
        if run is None:
            return

        now = datetime.now(UTC).isoformat()
        updated_stages = []
        for stage in run.stages:
            if isinstance(stage, dict):
                stage = _dict_to_stage_local(stage)
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
