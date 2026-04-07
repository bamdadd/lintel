"""Verify implementation completeness against the plan.

Compares plan tasks against actual file modifications in the sandbox
and computes a completeness score. Routes back to implement if too
many tasks are unaddressed (below COMPLETENESS_THRESHOLD) and retries
remain, otherwise proceeds to review.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import structlog

from lintel.workflows.base import WorkflowNode

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()

# A plan task is considered addressed if this fraction or more of tasks
# have corresponding file modifications.
COMPLETENESS_THRESHOLD: float = 0.8

# Maximum number of implement → verify loops before giving up.
MAX_IMPLEMENT_ATTEMPTS: int = 3


async def _get_modified_files(
    config: dict[str, Any],
    state: dict[str, Any],
) -> list[str]:
    """Get the list of files modified in the sandbox via ``git diff``."""
    from lintel.sandbox.types import SandboxJob

    configurable = config.get("configurable", {})
    sandbox_manager = configurable.get("sandbox_manager")
    if sandbox_manager is None:
        run_id = configurable.get("run_id") or state.get("run_id", "")
        if run_id:
            from lintel.workflows.nodes._runtime_registry import get_sandbox_manager

            sandbox_manager = get_sandbox_manager(str(run_id))

    sandbox_id = state.get("sandbox_id")
    if sandbox_manager is None or not sandbox_id:
        logger.warning("verify_impl_no_sandbox", sandbox_id=sandbox_id)
        return []

    workspace_path = state.get("workspace_path", "/workspace")

    # Use git diff against the base branch to find all modified files.
    # --name-only --diff-filter=ACMR lists Added, Copied, Modified, Renamed files.
    result = await sandbox_manager.execute(
        sandbox_id,
        SandboxJob(
            command="git diff --name-only --diff-filter=ACMR HEAD~100 HEAD 2>/dev/null"
            " || git diff --name-only --diff-filter=ACMR --cached 2>/dev/null"
            " || git diff --name-only 2>/dev/null"
            " || true",
            workdir=workspace_path,
            timeout_seconds=30,
        ),
    )
    output = getattr(result, "output", "") or ""
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return files


def _task_addressed(
    task: dict[str, Any],
    modified_files: list[str],
) -> bool:
    """Check whether a plan task is addressed by the modified files.

    Matches on:
    - Exact file_path match
    - Same filename (stem) in any directory
    - Same parent directory
    """
    file_path = task.get("file_path") or task.get("file") or ""
    if not file_path:
        # Tasks without a file_path are considered addressed by default
        # (e.g. "update documentation", "run tests").
        return True

    task_path = PurePosixPath(file_path)
    task_stem = task_path.stem
    task_parent = str(task_path.parent)

    for mod_file in modified_files:
        mod_path = PurePosixPath(mod_file)
        # Exact match (relative paths)
        if mod_file == file_path or str(mod_path) == str(task_path):
            return True
        # Same filename
        if mod_path.stem == task_stem and mod_path.suffix == task_path.suffix:
            return True
        # Same directory — any file changed in the target directory counts
        if str(mod_path.parent) == task_parent:
            return True
    return False


class VerifyImplementationNode(WorkflowNode):
    """Cross-references plan tasks against sandbox-verified modified files."""

    name: str = "verify_implementation"

    async def execute(
        self,
        state: ThreadWorkflowState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Run verification and return state updates."""
        from lintel.workflows.types import VerificationResult

        await self.tracker.append_log(
            self.name, "Verifying implementation completeness against plan..."
        )

        plan = state.get("plan", {})
        tasks: list[dict[str, Any]] = plan.get("tasks", [])

        if not tasks:
            # No tasks in plan — nothing to verify, pass through.
            result = VerificationResult(
                completeness_score=1.0,
                addressed_tasks=(),
                unaddressed_tasks=(),
                modified_files=(),
                attempt_count=state.get("implement_attempt_count", 0),
            )
            await self.tracker.append_log(self.name, "No plan tasks to verify — passing through.")
            await self._emit_verified(config, state, result)
            await self.complete(outputs={"completeness_score": 1.0})
            return {"verification_result": result, "verification_feedback": None}

        # Get ground-truth modified files from sandbox.
        try:
            modified_files = await _get_modified_files(dict(config), dict(state))
        except Exception as exc:
            logger.exception("verify_impl_sandbox_error", error=str(exc))
            await self.tracker.append_log(self.name, f"Failed to list modified files: {exc}")
            await self.complete(error=f"Sandbox error: {exc}")
            return {
                "error": f"verify_implementation failed: {exc}",
                "current_phase": "failed",
            }

        # Cross-reference tasks against modified files.
        addressed: list[str] = []
        unaddressed: list[str] = []
        for task in tasks:
            task_id = task.get("id") or task.get("title") or task.get("description", "unknown")
            if _task_addressed(task, modified_files):
                addressed.append(str(task_id))
            else:
                unaddressed.append(str(task_id))

        total = len(tasks)
        score = len(addressed) / total if total > 0 else 1.0
        attempt_count = state.get("implement_attempt_count", 0)

        result = VerificationResult(
            completeness_score=score,
            addressed_tasks=tuple(addressed),
            unaddressed_tasks=tuple(unaddressed),
            modified_files=tuple(modified_files),
            attempt_count=attempt_count,
        )

        await self.tracker.append_log(
            self.name,
            f"Completeness: {score:.0%} "
            f"({len(addressed)}/{total} tasks addressed, "
            f"attempt {attempt_count + 1}/{MAX_IMPLEMENT_ATTEMPTS})",
        )

        if unaddressed:
            await self.tracker.append_log(
                self.name,
                f"Unaddressed tasks: {', '.join(unaddressed[:10])}"
                + ("..." if len(unaddressed) > 10 else ""),
            )

        # Decide pass/fail.
        passes = score >= COMPLETENESS_THRESHOLD
        max_reached = attempt_count >= MAX_IMPLEMENT_ATTEMPTS

        if passes or max_reached:
            if max_reached and not passes:
                await self.tracker.append_log(
                    self.name,
                    f"Max attempts ({MAX_IMPLEMENT_ATTEMPTS}) reached — "
                    f"proceeding with {score:.0%} completeness.",
                )
            await self._emit_verified(config, state, result)
            await self.complete(
                outputs={
                    "completeness_score": score,
                    "addressed_count": len(addressed),
                    "total_count": total,
                }
            )
            return {
                "verification_result": result,
                "verification_feedback": None,
            }

        # Fail — route back to implement.
        feedback_lines = [
            "The following planned tasks were not addressed by the implementation:",
            "",
        ]
        for task in tasks:
            task_id = task.get("id") or task.get("title") or task.get("description", "unknown")
            if str(task_id) in unaddressed:
                desc = task.get("description", task.get("title", task_id))
                fp = task.get("file_path") or task.get("file") or ""
                feedback_lines.append(f"- {desc}" + (f" ({fp})" if fp else ""))

        feedback = "\n".join(feedback_lines)

        await self._emit_verification_failed(config, state, result)
        await self.complete(
            outputs={
                "completeness_score": score,
                "addressed_count": len(addressed),
                "total_count": total,
            }
        )
        return {
            "verification_result": result,
            "verification_feedback": feedback,
            "implement_attempt_count": attempt_count + 1,
        }

    # ------------------------------------------------------------------
    # Event emission helpers
    # ------------------------------------------------------------------

    async def _emit_verified(
        self,
        config: RunnableConfig,
        state: ThreadWorkflowState,
        result: Any,
    ) -> None:
        from lintel.workflows.events import ImplementationVerified

        self._emit_event(
            config,
            state,
            ImplementationVerified,
            result,
        )

    async def _emit_verification_failed(
        self,
        config: RunnableConfig,
        state: ThreadWorkflowState,
        result: Any,
    ) -> None:
        from lintel.workflows.events import ImplementationVerificationFailed

        self._emit_event(
            config,
            state,
            ImplementationVerificationFailed,
            result,
        )

    def _emit_event(
        self,
        config: RunnableConfig,
        state: ThreadWorkflowState,
        event_cls: type,
        result: Any,
    ) -> None:
        """Best-effort event emission via the event bus."""
        try:
            from dataclasses import asdict

            configurable = config.get("configurable", {})
            event_bus = configurable.get("event_bus")
            if event_bus is None:
                return

            payload = {
                "stage": "verify_implementation",
                "verification_result": asdict(result),
            }
            run_id = state.get("run_id", "")
            if run_id:
                payload["run_id"] = run_id

            event = event_cls(
                actor_id="system",
                payload=payload,
            )
            # Fire-and-forget — event bus may be sync or async.
            import asyncio

            loop = asyncio.get_event_loop()
            if hasattr(event_bus, "publish"):
                coro = event_bus.publish(event)
                if asyncio.iscoroutine(coro):
                    loop.create_task(coro)
        except Exception:
            logger.debug("verify_impl_event_emit_failed", exc_info=True)


def route_after_verification(state: ThreadWorkflowState) -> str:
    """Pure routing function for the conditional edge after verify_implementation.

    Returns:
        ``'review'`` — verification passed or max retries exceeded.
        ``'implement'`` — below threshold and retries remain.
        ``'close'`` — error or explicit failure.
    """
    if state.get("error"):
        return "close"

    result = state.get("verification_result")
    if result is None:
        # No verification result — pass through to review.
        return "review"

    score = result.completeness_score
    attempt_count = state.get("implement_attempt_count", 0)

    if score >= COMPLETENESS_THRESHOLD:
        return "review"
    if attempt_count >= MAX_IMPLEMENT_ATTEMPTS:
        return "review"
    # Below threshold and attempts remain — loop back.
    return "implement"
