"""Helper for updating stage status in pipeline runs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import structlog

logger = structlog.get_logger()

StageSuccessHook = Callable[[str, dict[str, object] | None], Awaitable[None]]
StageFailureHook = Callable[[str, str], Awaitable[None]]

# Map LangGraph node names to pipeline stage names.
NODE_TO_STAGE: dict[str, str] = {
    "triage": "triage",
    "analyse": "analyse",
    "ingest": "ingest",
    "route": "route",
    "setup_workspace": "setup_workspace",
    "research": "research",
    "approval_gate_research": "approve_research",
    "plan": "plan",
    "approval_gate_spec": "approve_spec",
    "implement": "implement",
    "test": "test",
    "review": "review",
    "approval_gate_pr": "approved_for_pr",
    "close": "raise_pr",
}


def _pattern_matches(pattern: str, event: str) -> bool:
    """Match a notification rule pattern against an event string.

    Supports: exact match, "*" (match all), "*.status", "stage.*".
    """
    if not pattern or pattern == "*":
        return True
    if pattern == event:
        return True
    # Wildcard matching: "*.succeeded" or "research.*"
    p_parts = pattern.split(".")
    e_parts = event.split(".")
    if len(p_parts) != len(e_parts):
        return False
    return all(p == "*" or p == e for p, e in zip(p_parts, e_parts, strict=True))


class StageTracker:
    """Encapsulates pipeline stage lifecycle operations for a LangGraph node run."""

    def __init__(
        self,
        config: Mapping[str, Any],
        state: Mapping[str, Any] | None = None,
        *,
        on_success: StageSuccessHook | None = None,
        on_failure: StageFailureHook | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._run_id: str | None = None
        self._pipeline_store: Any | None = _SENTINEL
        self._on_success = on_success
        self._on_failure = on_failure

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def run_id(self) -> str:
        if self._run_id is None:
            self._run_id = _get_run_id(self._config, self._state)
        return self._run_id

    @property
    def pipeline_store(self) -> Any:  # noqa: ANN401
        if self._pipeline_store is _SENTINEL:
            self._pipeline_store = _get_pipeline_store(self._config, self._state)
        return self._pipeline_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def mark_running(
        self,
        node_name: str,
        inputs: dict[str, object] | None = None,
    ) -> None:
        """Mark a pipeline stage as running. Call at the start of a node.

        If the stage was previously completed (re-entry during a loop), the
        previous execution is archived as a StageAttempt and the stage is reset.
        """
        stage_name = NODE_TO_STAGE.get(node_name)
        if not stage_name:
            return
        if not self.run_id:
            return
        await self._archive_and_reset(stage_name, inputs=inputs)

    async def append_log(self, node_name: str, line: str) -> None:
        """Append a log line to a pipeline stage. Call during node execution."""
        stage_name = NODE_TO_STAGE.get(node_name)
        if not stage_name:
            return
        if not self.run_id:
            return

        from lintel.workflows.types import Stage

        pipeline_store = self.pipeline_store
        if pipeline_store is None:
            return

        run = await pipeline_store.get(self.run_id)
        if run is None:
            return

        from lintel.workflows.types import PipelineRun

        new_stages: list[Stage] = []
        for s in run.stages:
            if s.name == stage_name:
                existing_logs = list(s.logs) if s.logs else []
                existing_logs.append(line)
                new_stages.append(
                    Stage(
                        stage_id=s.stage_id,
                        name=s.name,
                        stage_type=s.stage_type,
                        status=s.status,
                        inputs=s.inputs,
                        outputs=s.outputs,
                        error=s.error,
                        duration_ms=s.duration_ms,
                        started_at=s.started_at,
                        finished_at=s.finished_at,
                        logs=tuple(existing_logs),
                        retry_count=s.retry_count,
                        attempts=s.attempts,
                    )
                )
            else:
                new_stages.append(s)

        updated = PipelineRun(
            run_id=run.run_id,
            project_id=run.project_id,
            work_item_id=run.work_item_id,
            workflow_definition_id=run.workflow_definition_id,
            status=run.status,
            stages=tuple(new_stages),
            trigger_type=run.trigger_type,
            trigger_id=run.trigger_id,
            environment_id=run.environment_id,
            created_at=run.created_at,
        )
        try:
            await pipeline_store.update(updated)
        except Exception:
            logger.warning("append_log_failed", run_id=self.run_id, stage_name=stage_name)

    async def mark_completed(
        self,
        node_name: str,
        outputs: dict[str, object] | None = None,
        error: str = "",
    ) -> None:
        """Mark a pipeline stage as succeeded or failed. Call at the end of a node."""
        stage_name = NODE_TO_STAGE.get(node_name)
        if not stage_name:
            return
        if not self.run_id:
            return
        status = "failed" if error else "succeeded"
        await self._update_stage(stage_name, status, outputs=outputs, error=error)
        await self._dispatch_notifications(stage_name, status)
        # Lifecycle hooks
        if error and self._on_failure is not None:
            try:
                await self._on_failure(node_name, error)
            except Exception:
                logger.warning("on_failure_hook_error", node_name=node_name)
        elif not error and self._on_success is not None:
            try:
                await self._on_success(node_name, outputs)
            except Exception:
                logger.warning("on_success_hook_error", node_name=node_name)

    async def log_llm_context(
        self,
        node_name: str,
        agent_role: str,
        step_name: str,
    ) -> None:
        """Log which agent, provider, model, and skill is being used for an LLM call."""
        configurable = self._config.get("configurable", {})
        agent_runtime = configurable.get("agent_runtime")
        if agent_runtime is None:
            run_id = self.run_id
            if run_id:
                from lintel.workflows.nodes._runtime_registry import get_runtime

                agent_runtime = get_runtime(run_id)
        if agent_runtime is None:
            return

        try:
            router = agent_runtime._model_router
            from lintel.agents.types import AgentRole

            role_enum = AgentRole(agent_role) if isinstance(agent_role, str) else agent_role
            policy = await router.select_model(role_enum, step_name)
            line = f"Agent: {agent_role} | Provider: {policy.provider} | Model: {policy.model_name}"
            await self.append_log(node_name, line)
        except Exception:
            logger.debug("log_llm_context_failed", node_name=node_name)

    @staticmethod
    def extract_token_usage(result: dict[str, Any]) -> dict[str, int]:
        """Extract token usage info from an AgentRuntime.execute_step() result."""
        usage = result.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _update_stage(
        self,
        stage_name: str,
        status: str,
        outputs: dict[str, object] | None = None,
        error: str = "",
    ) -> None:
        from lintel.workflows.types import Stage, StageStatus

        pipeline_store = self.pipeline_store
        if pipeline_store is None:
            return

        run = await pipeline_store.get(self.run_id)
        if run is None:
            logger.warning("stage_update_run_not_found", run_id=self.run_id)
            return

        new_stages: list[Stage] = []
        found = False
        for s in run.stages:
            if s.name == stage_name:
                found = True
                new_stages.append(
                    Stage(
                        stage_id=s.stage_id,
                        name=s.name,
                        stage_type=s.stage_type,
                        status=StageStatus(status),
                        inputs=s.inputs,
                        outputs=outputs if outputs is not None else s.outputs,
                        error=error or s.error,
                        duration_ms=s.duration_ms,
                        started_at=s.started_at,
                        finished_at=s.finished_at,
                        logs=s.logs,
                        retry_count=s.retry_count,
                        attempts=s.attempts,
                    )
                )
            else:
                new_stages.append(s)

        if not found:
            logger.warning(
                "stage_not_found_in_run",
                run_id=self.run_id,
                stage_name=stage_name,
            )
            return

        from lintel.workflows.types import PipelineRun

        updated = PipelineRun(
            run_id=run.run_id,
            project_id=run.project_id,
            work_item_id=run.work_item_id,
            workflow_definition_id=run.workflow_definition_id,
            status=run.status,
            stages=tuple(new_stages),
            trigger_type=run.trigger_type,
            trigger_id=run.trigger_id,
            environment_id=run.environment_id,
            created_at=run.created_at,
        )
        try:
            await pipeline_store.update(updated)
        except Exception:
            logger.warning("stage_update_failed", run_id=self.run_id, stage_name=stage_name)

    async def _archive_and_reset(
        self,
        stage_name: str,
        inputs: dict[str, object] | None = None,
    ) -> None:
        """If a stage was previously completed, archive its data as an attempt and reset."""
        from datetime import UTC, datetime

        from lintel.workflows.types import PipelineRun, Stage, StageAttempt, StageStatus

        pipeline_store = self.pipeline_store
        if pipeline_store is None:
            return

        run = await pipeline_store.get(self.run_id)
        if run is None:
            return

        now = datetime.now(tz=UTC).isoformat()
        new_stages: list[Stage] = []
        for s in run.stages:
            if s.name == stage_name:
                attempts = list(s.attempts)
                if s.status not in (StageStatus.PENDING,):
                    attempts.append(
                        StageAttempt(
                            attempt=len(attempts) + 1,
                            status=s.status,
                            inputs=s.inputs,
                            outputs=s.outputs,
                            error=s.error,
                            duration_ms=s.duration_ms,
                            started_at=s.started_at,
                            finished_at=s.finished_at,
                            logs=s.logs,
                        )
                    )
                new_stages.append(
                    Stage(
                        stage_id=s.stage_id,
                        name=s.name,
                        stage_type=s.stage_type,
                        status=StageStatus.RUNNING,
                        inputs=inputs,
                        outputs=None,
                        error="",
                        duration_ms=0,
                        started_at=now,
                        finished_at="",
                        logs=(),
                        retry_count=len(attempts),
                        attempts=tuple(attempts),
                    )
                )
            else:
                new_stages.append(s)

        updated = PipelineRun(
            run_id=run.run_id,
            project_id=run.project_id,
            work_item_id=run.work_item_id,
            workflow_definition_id=run.workflow_definition_id,
            status=run.status,
            stages=tuple(new_stages),
            trigger_type=run.trigger_type,
            trigger_id=run.trigger_id,
            environment_id=run.environment_id,
            created_at=run.created_at,
        )
        try:
            await pipeline_store.update(updated)
        except Exception:
            logger.warning("archive_and_reset_failed", run_id=self.run_id, stage_name=stage_name)

    async def _dispatch_notifications(self, stage_name: str, status: str) -> None:
        """Evaluate notification rules and dispatch matching ones."""
        configurable = self._config.get("configurable", {})
        app_state = configurable.get("app_state")
        if app_state is None:
            run_id = self.run_id
            if run_id:
                from lintel.workflows.nodes._runtime_registry import get_app_state

                app_state = get_app_state(run_id)
        if app_state is None:
            return

        notification_rule_store = getattr(app_state, "notification_rule_store", None)
        if notification_rule_store is None:
            return

        try:
            rules = await notification_rule_store.list_all()
        except Exception:
            logger.debug("notification_rules_fetch_failed")
            return

        event_pattern = f"{stage_name}.{status}"

        for rule in rules:
            if not getattr(rule, "enabled", True):
                continue
            pattern = getattr(rule, "event_pattern", "")
            if not _pattern_matches(pattern, event_pattern):
                continue

            rule_project_id = getattr(rule, "project_id", "")
            if rule_project_id:
                pipeline_store = self.pipeline_store
                if pipeline_store:
                    run = await pipeline_store.get(self.run_id)
                    if run and getattr(run, "project_id", "") != rule_project_id:
                        continue

            channel = getattr(rule, "channel", "")
            target = getattr(rule, "target", "")
            if channel == "slack" and target:
                channel_adapter = getattr(app_state, "channel_adapter", None)
                if channel_adapter is not None:
                    try:
                        run_short = self.run_id[:12]
                        message = f"Stage *{stage_name}* is now *{status}* (run: {run_short})"
                        await channel_adapter.send_message(
                            channel_id=target,
                            thread_ts="",
                            text=message,
                        )
                    except Exception:
                        logger.warning(
                            "notification_dispatch_failed",
                            rule_id=getattr(rule, "rule_id", ""),
                            channel=channel,
                        )


# Sentinel for lazy-init of pipeline_store
_SENTINEL: object = object()


# ---------------------------------------------------------------------------
# Module-level backward-compatible wrappers
# ---------------------------------------------------------------------------


async def mark_running(
    config: Mapping[str, Any],
    node_name: str,
    state: Mapping[str, Any] | None = None,
    inputs: dict[str, object] | None = None,
) -> None:
    """Mark a pipeline stage as running. Call at the start of a node."""
    await StageTracker(config, state).mark_running(node_name, inputs=inputs)


async def append_log(
    config: Mapping[str, Any],
    node_name: str,
    line: str,
    state: Mapping[str, Any] | None = None,
) -> None:
    """Append a log line to a pipeline stage. Call during node execution."""
    await StageTracker(config, state).append_log(node_name, line)


async def mark_completed(
    config: Mapping[str, Any],
    node_name: str,
    state: Mapping[str, Any] | None = None,
    outputs: dict[str, object] | None = None,
    error: str = "",
) -> None:
    """Mark a pipeline stage as succeeded or failed. Call at the end of a node."""
    await StageTracker(config, state).mark_completed(node_name, outputs=outputs, error=error)


async def log_llm_context(
    config: Mapping[str, Any],
    node_name: str,
    agent_role: str,
    step_name: str,
    state: Mapping[str, Any] | None = None,
) -> None:
    """Log which agent, provider, model, and skill is being used for an LLM call."""
    await StageTracker(config, state).log_llm_context(node_name, agent_role, step_name)


def extract_token_usage(node_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Extract token usage info from an AgentRuntime.execute_step() result."""
    usage = result.get("usage", {})
    return {
        "node": node_name,
        "model": result.get("model", ""),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }


async def update_stage(
    config: Mapping[str, Any],
    run_id: str,
    stage_name: str,
    status: str,
    outputs: dict[str, object] | None = None,
    error: str = "",
    state: Mapping[str, Any] | None = None,
) -> None:
    """Update a stage's status within a pipeline run."""
    tracker = StageTracker(config, state)
    tracker._run_id = run_id
    await tracker._update_stage(stage_name, status, outputs=outputs, error=error)


def _get_pipeline_store(
    config: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
) -> Any:  # noqa: ANN401
    """Extract pipeline_store from LangGraph configurable dict."""
    configurable = config.get("configurable", {})
    store = configurable.get("pipeline_store")
    if store is not None:
        return store
    app_state = configurable.get("app_state")
    if app_state is None:
        run_id = config.get("configurable", {}).get("run_id", "")
        if not run_id and state:
            run_id = state.get("run_id", "")
        if run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            app_state = get_app_state(str(run_id))
    if app_state is None:
        return None
    return getattr(app_state, "pipeline_store", None)


def _get_run_id(config: Mapping[str, Any], state: Mapping[str, Any] | None = None) -> str:
    """Extract run_id from config or state."""
    run_id = config.get("configurable", {}).get("run_id", "")
    if not run_id and state:
        run_id = state.get("run_id", "")
    return str(run_id)
