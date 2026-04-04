"""SlackChangeRequestHandler — detects change requests on completed workflow threads.

When a user replies to a completed workflow Slack thread with change requests,
this handler parses the feedback, looks up the original pipeline run to recover
the branch/PR/project context, and dispatches a new implement cycle on the same
branch so the changes are applied incrementally.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()

# Patterns that indicate a change request (case-insensitive)
_CHANGE_REQUEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bchange\s+(this|that|the)\b", re.IGNORECASE),
    re.compile(r"\bplease\s+(update|modify|fix|change|adjust|revise)\b", re.IGNORECASE),
    re.compile(r"\bcan\s+you\s+(update|modify|fix|change|adjust|revise)\b", re.IGNORECASE),
    re.compile(r"\b(update|modify|fix|change|adjust|revise)\s+(the|this|that)\b", re.IGNORECASE),
    re.compile(r"\binstead\s+(of|,)\b", re.IGNORECASE),
    re.compile(r"\bactually\s*,?\s*(i|we|let's|can)\b", re.IGNORECASE),
    re.compile(r"\brename\b", re.IGNORECASE),
    re.compile(r"\bremove\b", re.IGNORECASE),
    re.compile(r"\breplace\b", re.IGNORECASE),
    re.compile(r"\bmove\b.*\bto\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\b.*\binstead\b", re.IGNORECASE),
    re.compile(r"\bshould\s+(be|have|use)\b", re.IGNORECASE),
    re.compile(r"\bneeds?\s+(to|a|some)\b", re.IGNORECASE),
)


def is_change_request(text: str) -> bool:
    """Return True if the message text looks like a change request on prior work."""
    if not text or len(text.strip()) < 10:
        return False
    return any(p.search(text) for p in _CHANGE_REQUEST_PATTERNS)


class SlackChangeRequestHandler:
    """Handles change requests from Slack threads on completed workflows.

    Workflow:
    1. Detect that a message in a completed-workflow thread is a change request.
    2. Look up the original pipeline run to recover context (branch, PR, project).
    3. Dispatch a ``change_request`` workflow that re-enters implement → review → close
       on the same feature branch, applying the user's feedback as the new task.
    """

    def __init__(
        self,
        pipeline_store: Any,  # noqa: ANN401
        work_item_store: Any,  # noqa: ANN401
    ) -> None:
        self._pipeline_store = pipeline_store
        self._work_item_store = work_item_store

    async def find_completed_run_for_thread(
        self,
        thread_ref: ThreadRef,
    ) -> Any:  # noqa: ANN401
        """Find a completed/succeeded pipeline run associated with a thread.

        Searches pipeline runs by trigger_type matching the thread's conversation ID.
        Returns the pipeline run or None if no completed run is found.
        """
        all_runs = await self._pipeline_store.list_all()
        thread_ts = thread_ref.thread_ts

        for run in all_runs:
            trigger_type = (
                run.trigger_type if hasattr(run, "trigger_type") else run.get("trigger_type", "")
            )
            status = run.status if hasattr(run, "status") else run.get("status", "")

            # Match by conversation ID in trigger_type (format: "chat:{conversation_id}")
            if f"chat:{thread_ts}" in str(trigger_type) and str(status) in (
                "succeeded",
                "failed",
            ):
                return run
        return None

    async def extract_change_context(
        self,
        run: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Extract the context needed to dispatch a change request workflow.

        Pulls branch name, PR URL, project ID, repo URL, work item, and sandbox
        info from the completed pipeline run.
        """
        run_id = run.run_id if hasattr(run, "run_id") else run.get("run_id", "")
        project_id = run.project_id if hasattr(run, "project_id") else run.get("project_id", "")
        work_item_id = (
            run.work_item_id if hasattr(run, "work_item_id") else run.get("work_item_id", "")
        )
        workflow_def_id = (
            run.workflow_definition_id
            if hasattr(run, "workflow_definition_id")
            else run.get("workflow_definition_id", "")
        )

        # Look up work item for branch name and PR URL
        feature_branch = ""
        pr_url = ""
        repo_url = ""
        if work_item_id and self._work_item_store is not None:
            item = await self._work_item_store.get(work_item_id)
            if item is not None:
                feature_branch = (
                    item.get("branch_name", "")
                    if isinstance(item, dict)
                    else getattr(item, "branch_name", "")
                )
                pr_url = (
                    item.get("pr_url", "")
                    if isinstance(item, dict)
                    else getattr(item, "pr_url", "")
                )

        # Extract stage outputs for additional context
        stages = run.stages if hasattr(run, "stages") else run.get("stages", ())
        for stage in stages:
            s_outputs = (
                stage.outputs
                if hasattr(stage, "outputs")
                else (stage.get("outputs") if isinstance(stage, dict) else None)
            )
            if s_outputs and isinstance(s_outputs, dict) and not pr_url and s_outputs.get("pr_url"):
                pr_url = str(s_outputs["pr_url"])

        return {
            "original_run_id": run_id,
            "project_id": project_id,
            "work_item_id": work_item_id,
            "workflow_definition_id": workflow_def_id,
            "feature_branch": feature_branch,
            "pr_url": pr_url,
            "repo_url": repo_url,
        }
