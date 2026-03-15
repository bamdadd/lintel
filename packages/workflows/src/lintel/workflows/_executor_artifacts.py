"""Work item and approval lifecycle helpers extracted from WorkflowExecutor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from lintel.domain.events import WorkItemUpdated

if TYPE_CHECKING:
    from lintel.contracts.protocols import EventStore

logger = structlog.get_logger()


async def is_auto_move_enabled(app_state: Any, project_id: str) -> bool:
    """Check if any board for this project has auto_move enabled."""
    if app_state is None:
        return False
    board_store = getattr(app_state, "board_store", None)
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


async def evaluate_policy(app_state: Any, run_id: str, node_name: str) -> str:
    """Evaluate policy for an approval gate. Returns action string."""
    if app_state is None:
        return "require_approval"
    try:
        from lintel.workflows.nodes._policy import evaluate_gate_policy
        from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

        policy_store = getattr(app_state, "policy_store", None)
        pipeline_store = getattr(app_state, "pipeline_store", None)

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


async def create_approval_request(app_state: Any, run_id: str, node_name: str) -> None:
    """Create an ApprovalRequest record when workflow pauses at an approval gate."""
    if app_state is None:
        return
    approval_store = getattr(app_state, "approval_request_store", None)
    if approval_store is None:
        return
    try:
        from lintel.domain.types import ApprovalRequest
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


def _dict_to_stage_local(d: dict[str, Any]) -> Any:
    """Convert a plain dict to a Stage dataclass instance."""
    import contextlib

    from lintel.workflows.types import Stage, StageStatus
    from dataclasses import fields as dc_fields

    valid = {f.name for f in dc_fields(Stage)}
    filtered = {k: v for k, v in d.items() if k in valid}
    if "status" in filtered and isinstance(filtered["status"], str):
        with contextlib.suppress(ValueError):
            filtered["status"] = StageStatus(filtered["status"])
    return Stage(**filtered)


async def rehydrate_from_run(app_state: Any, prev_run_id: str) -> dict[str, Any]:
    """Load stage outputs from a previous run and map them to workflow state keys."""
    import contextlib

    from lintel.workflows.types import StageStatus

    result: dict[str, Any] = {}
    if app_state is None:
        return result
    pipeline_store = getattr(app_state, "pipeline_store", None)
    if pipeline_store is None:
        return result
    try:
        run = await pipeline_store.get(prev_run_id)
        if run is None:
            logger.warning("rehydrate_run_not_found", run_id=prev_run_id)
            return result
        for stage in run.stages:
            if isinstance(stage, dict):
                stage = _dict_to_stage_local(stage)
            outputs = stage.outputs if isinstance(stage.outputs, dict) else {}
            if stage.status == StageStatus.SUCCEEDED and outputs:
                if stage.name == "research" and (
                    "research_report" in outputs or "research_context" in outputs
                ):
                    result["research_context"] = outputs.get(
                        "research_report", outputs.get("research_context", "")
                    )
                elif stage.name == "plan" and "plan" in outputs:
                    result["plan"] = outputs["plan"]
                elif stage.name == "setup_workspace" and "feature_branch" in outputs:
                    result["feature_branch"] = outputs["feature_branch"]
            elif stage.status == StageStatus.FAILED and stage.error:
                result["previous_error"] = stage.error
                result["previous_failed_stage"] = stage.name
        logger.info(
            "rehydrated_from_previous_run",
            prev_run_id=prev_run_id,
            keys=list(result.keys()),
        )
    except Exception:
        logger.warning("rehydrate_failed", prev_run_id=prev_run_id, exc_info=True)
    return result


async def fail_work_item(
    app_state: Any,
    event_store: EventStore,
    project_events_fn: Any,
    run_id: str,
    work_item_id: str,
    project_id: str,
) -> None:
    """Mark the work item as failed (or open if auto_move is on)."""
    if app_state is None:
        return
    work_item_store = getattr(app_state, "work_item_store", None)
    if work_item_store is None or not work_item_id:
        return
    try:
        item = await work_item_store.get(work_item_id)
        if item is None:
            return
        item_project_id = item.get("project_id", "") or project_id
        auto_move = await is_auto_move_enabled(app_state, item_project_id)
        new_status = "open" if auto_move else "failed"
        item["status"] = new_status
        await work_item_store.update(work_item_id, item)
        # Emit audit event for work item failure
        stream_id = f"work_item:{work_item_id}"
        event = WorkItemUpdated(
            event_type="WorkItemUpdated",
            payload={
                "work_item_id": work_item_id,
                "status": new_status,
                "auto_moved": auto_move,
            },
        )
        await event_store.append(stream_id=stream_id, events=[event])
        await project_events_fn([event])
        if auto_move:
            logger.info(
                "auto_move_failed_to_todo",
                work_item_id=work_item_id,
            )
            # Item moved from in_progress to open — WIP capacity freed
            # Exclude the just-failed item from promotion
            await auto_promote_if_capacity(
                app_state,
                event_store,
                project_events_fn,
                item_project_id,
                work_item_store,
                exclude_id=work_item_id,
            )
    except Exception as exc:
        logger.warning(
            "fail_work_item_failed",
            work_item_id=work_item_id,
            error=str(exc),
        )


async def complete_work_item(
    app_state: Any,
    event_store: EventStore,
    project_events_fn: Any,
    work_item_id: str,
) -> None:
    """Mark the work item as closed after workflow success."""
    from lintel.domain.events import WorkItemCompleted

    if app_state is None:
        return
    work_item_store = getattr(app_state, "work_item_store", None)
    if work_item_store is None or not work_item_id:
        return
    try:
        item = await work_item_store.get(work_item_id)
        if item is None:
            return
        item["status"] = "closed"
        await work_item_store.update(work_item_id, item)
        # Emit audit event for work item completion
        stream_id = f"work_item:{work_item_id}"
        event = WorkItemCompleted(
            event_type="WorkItemCompleted",
            payload={
                "work_item_id": work_item_id,
                "status": "closed",
            },
        )
        await event_store.append(stream_id=stream_id, events=[event])
        await project_events_fn([event])
        # Auto-promote: if auto_move is on and WIP has capacity, move oldest open item
        project_id = item.get("project_id", "")
        await auto_promote_if_capacity(
            app_state, event_store, project_events_fn, project_id, work_item_store
        )
    except Exception as exc:
        logger.warning(
            "complete_work_item_failed", work_item_id=work_item_id, error=str(exc)
        )


async def auto_promote_if_capacity(
    app_state: Any,
    event_store: EventStore,
    project_events_fn: Any,
    project_id: str,
    work_item_store: object,
    *,
    exclude_id: str = "",
) -> None:
    """Promote the oldest open work item to in_progress if WIP has capacity."""
    if not project_id or app_state is None:
        return
    if not await is_auto_move_enabled(app_state, project_id):
        return
    board_store = getattr(app_state, "board_store", None)
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
            await event_store.append(stream_id=stream_id, events=[event])
            await project_events_fn([event])
    except Exception as exc:
        logger.warning(
            "auto_promote_failed",
            project_id=project_id,
            error=str(exc),
        )
