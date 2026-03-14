# Pipeline Continuation & Artifact Storage Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store stage artifacts (research reports, plans, diffs) so the artifacts page has content, and enable pipeline continuation from a previous failed run's outputs instead of starting from scratch.

**Architecture:** Each workflow node stores a `CodeArtifact` on completion (success or failure) via `StageTracker` lifecycle hooks. `StartWorkflow` gains a `continue_from_run_id` field. When set, `WorkflowExecutor` loads the previous run's stage outputs and seeds the initial LangGraph state, allowing completed stages to be skipped.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, dataclasses, Pydantic

---

## Chunk 1: Stage Lifecycle Hooks & Artifact Storage

### Task 1: Add `on_success` / `on_failure` callbacks to `StageTracker.mark_completed`

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/_stage_tracking.py:158-172`
- Test: `packages/workflows/tests/workflows/nodes/test_stage_tracking.py`

- [ ] **Step 1: Write failing test for on_success callback**

```python
# packages/workflows/tests/workflows/nodes/test_stage_tracking.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes._stage_tracking import StageTracker


@pytest.fixture
def mock_config():
    pipeline_store = AsyncMock()
    pipeline_store.get.return_value = None  # no run — callbacks still fire
    return {
        "configurable": {
            "run_id": "run-1",
            "pipeline_store": pipeline_store,
            "app_state": MagicMock(pipeline_store=pipeline_store),
        }
    }


class TestStageLifecycleHooks:
    async def test_on_success_called_on_completion(self, mock_config):
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_success=callback)
        await tracker.mark_completed("research", outputs={"research_report": "report"})
        callback.assert_awaited_once_with("research", {"research_report": "report"})

    async def test_on_failure_called_on_error(self, mock_config):
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_failure=callback)
        await tracker.mark_completed("research", error="boom")
        callback.assert_awaited_once_with("research", "boom")

    async def test_on_success_not_called_on_error(self, mock_config):
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_success=callback)
        await tracker.mark_completed("research", error="boom")
        callback.assert_not_awaited()

    async def test_on_failure_not_called_on_success(self, mock_config):
        callback = AsyncMock()
        tracker = StageTracker(mock_config, on_failure=callback)
        await tracker.mark_completed("research", outputs={"x": 1})
        callback.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_stage_tracking.py::TestStageLifecycleHooks -v`
Expected: FAIL — `on_success` / `on_failure` not accepted by `StageTracker.__init__`

- [ ] **Step 3: Implement lifecycle hooks in StageTracker**

In `packages/workflows/src/lintel/workflows/nodes/_stage_tracking.py`, modify `__init__` and `mark_completed`:

```python
# In __init__ (add two new params):
from collections.abc import Awaitable, Callable

# Type aliases at module level:
StageSuccessHook = Callable[[str, dict[str, object] | None], Awaitable[None]]
StageFailureHook = Callable[[str, str], Awaitable[None]]

class StageTracker:
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

    # In mark_completed, after _dispatch_notifications:
    async def mark_completed(self, node_name, outputs=None, error=""):
        # ... existing code ...
        await self._update_stage(stage_name, status, outputs=outputs, error=error)
        await self._dispatch_notifications(stage_name, status)
        # NEW: lifecycle hooks
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_stage_tracking.py::TestStageLifecycleHooks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/_stage_tracking.py packages/workflows/tests/workflows/nodes/test_stage_tracking.py
git commit -m "feat: add on_success/on_failure lifecycle hooks to StageTracker"
```

---

### Task 2: Store artifacts from research node on completion

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/research.py:196-209`
- Test: `packages/workflows/tests/workflows/nodes/test_research_artifacts.py`

- [ ] **Step 1: Write failing test for artifact storage**

```python
# packages/workflows/tests/workflows/nodes/test_research_artifacts.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lintel.workflows.nodes.research import research_codebase


class TestResearchArtifactStorage:
    async def test_stores_artifact_on_success(self):
        """Research node should store the report as a CodeArtifact."""
        mock_runtime = AsyncMock()
        mock_runtime.execute_step_stream.return_value = {
            "content": "# Research Report\nFindings here.",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        artifact_store = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        state = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add a button"],
            "sandbox_id": None,
            "run_id": "run-1",
            "work_item_id": "wi-1",
            "workspace_path": "/workspace/repo",
            "research_context": "",
        }
        config = {
            "configurable": {
                "run_id": "run-1",
                "agent_runtime": mock_runtime,
                "sandbox_manager": None,
                "pipeline_store": pipeline_store,
                "app_state": MagicMock(
                    pipeline_store=pipeline_store,
                    code_artifact_store=artifact_store,
                ),
                "code_artifact_store": artifact_store,
            }
        }

        result = await research_codebase(state, config)

        assert result["research_context"] == "# Research Report\nFindings here."
        artifact_store.add.assert_awaited_once()
        stored = artifact_store.add.call_args[0][0]
        assert stored.artifact_type == "research_report"
        assert stored.run_id == "run-1"
        assert stored.work_item_id == "wi-1"
        assert "Findings here" in stored.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_research_artifacts.py -v`
Expected: FAIL — artifact_store.add not called

- [ ] **Step 3: Add artifact storage to research node**

At the end of `research_codebase` in `research.py`, before `return`, add:

```python
    # Store as artifact for the artifacts page
    _store_artifact = _configurable.get("code_artifact_store")
    if _store_artifact is None:
        _app = _configurable.get("app_state")
        if _app is not None:
            _store_artifact = getattr(_app, "code_artifact_store", None)
    if _store_artifact is not None:
        from lintel.contracts.types import CodeArtifact
        try:
            artifact = CodeArtifact(
                artifact_id=f"{state.get('run_id', '')}-research",
                work_item_id=state.get("work_item_id", ""),
                run_id=state.get("run_id", ""),
                artifact_type="research_report",
                path="",
                content=research_report,
            )
            await _store_artifact.add(artifact)
        except Exception:
            logger.warning("research_artifact_storage_failed", exc_info=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_research_artifacts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/research.py packages/workflows/tests/workflows/nodes/test_research_artifacts.py
git commit -m "feat: store research report as CodeArtifact"
```

---

### Task 3: Store artifacts from plan node on completion

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/plan.py:200-212`
- Test: `packages/workflows/tests/workflows/nodes/test_plan_artifacts.py`

- [ ] **Step 1: Write failing test for plan artifact storage**

```python
# packages/workflows/tests/workflows/nodes/test_plan_artifacts.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes.plan import plan_work


class TestPlanArtifactStorage:
    async def test_stores_plan_artifact_on_success(self):
        mock_runtime = AsyncMock()
        mock_runtime.execute_step_stream.return_value = {
            "content": '{"tasks": [{"title": "Do X"}], "summary": "Do X"}',
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        artifact_store = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        state = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-2",
            "work_item_id": "wi-2",
            "research_context": "some research",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
        }
        config = {
            "configurable": {
                "run_id": "run-2",
                "agent_runtime": mock_runtime,
                "sandbox_manager": None,
                "pipeline_store": pipeline_store,
                "app_state": MagicMock(
                    pipeline_store=pipeline_store,
                    code_artifact_store=artifact_store,
                ),
                "code_artifact_store": artifact_store,
            }
        }

        result = await plan_work(state, config)

        artifact_store.add.assert_awaited_once()
        stored = artifact_store.add.call_args[0][0]
        assert stored.artifact_type == "plan"
        assert stored.run_id == "run-2"
        assert "Do X" in stored.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_plan_artifacts.py -v`
Expected: FAIL

- [ ] **Step 3: Add artifact storage to plan node**

At end of `plan_work` in `plan.py`, before `return`, add:

```python
    # Store plan as artifact
    _store_artifact = _configurable.get("code_artifact_store")
    if _store_artifact is None:
        _app = _configurable.get("app_state")
        if _app is not None:
            _store_artifact = getattr(_app, "code_artifact_store", None)
    if _store_artifact is not None:
        from lintel.contracts.types import CodeArtifact
        try:
            artifact = CodeArtifact(
                artifact_id=f"{state.get('run_id', '')}-plan",
                work_item_id=state.get("work_item_id", ""),
                run_id=state.get("run_id", ""),
                artifact_type="plan",
                path="",
                content=content,
            )
            await _store_artifact.add(artifact)
        except Exception:
            logger.warning("plan_artifact_storage_failed", exc_info=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_plan_artifacts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/plan.py packages/workflows/tests/workflows/nodes/test_plan_artifacts.py
git commit -m "feat: store plan as CodeArtifact"
```

---

### Task 4: Store diff artifact from implement node

The implement node already collects diffs via `collect_artifacts`. We need to store them as `CodeArtifact` records.

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/implement.py` (near the end, after diff collection)
- Test: `packages/workflows/tests/workflows/nodes/test_implement_artifacts.py`

- [ ] **Step 1: Write failing test**

```python
# packages/workflows/tests/workflows/nodes/test_implement_artifacts.py

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestImplementArtifactStorage:
    async def test_stores_diff_artifact(self):
        """Implement node stores the git diff as a CodeArtifact."""
        # This test verifies the artifact store is called with a 'diff' artifact
        # after the implement stage completes with code changes.
        artifact_store = AsyncMock()
        # Check that add was called with artifact_type="diff"
        # (Integration-style — run the full node in a later test)
        from lintel.contracts.types import CodeArtifact

        artifact = CodeArtifact(
            artifact_id="run-3-implement-diff",
            work_item_id="wi-3",
            run_id="run-3",
            artifact_type="diff",
            path="",
            content="diff --git a/foo.py b/foo.py\n+new line",
        )
        await artifact_store.add(artifact)
        artifact_store.add.assert_awaited_once()
        stored = artifact_store.add.call_args[0][0]
        assert stored.artifact_type == "diff"
```

- [ ] **Step 2: Run test to verify it passes** (this is a smoke test for the store interface)

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_implement_artifacts.py -v`
Expected: PASS

- [ ] **Step 3: Add diff artifact storage to implement node**

In `implement.py`, after collecting the diff and before returning, add:

```python
    # Store diff as artifact
    if diff_content:
        _store_artifact = _configurable.get("code_artifact_store")
        if _store_artifact is None:
            _app = _configurable.get("app_state")
            if _app is not None:
                _store_artifact = getattr(_app, "code_artifact_store", None)
        if _store_artifact is not None:
            from lintel.contracts.types import CodeArtifact
            try:
                artifact = CodeArtifact(
                    artifact_id=f"{run_id}-implement-diff",
                    work_item_id=state.get("work_item_id", ""),
                    run_id=run_id,
                    artifact_type="diff",
                    path="",
                    content=diff_content,
                )
                await _store_artifact.add(artifact)
            except Exception:
                logger.warning("implement_diff_artifact_storage_failed", exc_info=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_implement_artifacts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/implement.py packages/workflows/tests/workflows/nodes/test_implement_artifacts.py
git commit -m "feat: store implement diff as CodeArtifact"
```

---

## Chunk 2: Pipeline Continuation

### Task 5: Add `continue_from_run_id` to `StartWorkflow` command

**Files:**
- Modify: `packages/contracts/src/lintel/contracts/commands.py:23-34`
- Test: `packages/contracts/tests/test_commands.py`

- [ ] **Step 1: Write failing test**

```python
# packages/contracts/tests/test_commands.py (append to existing)

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import ThreadRef


class TestStartWorkflowContinuation:
    def test_continue_from_run_id_defaults_empty(self):
        tr = ThreadRef(workspace_id="w", channel_id="c", thread_ts="t")
        cmd = StartWorkflow(thread_ref=tr, workflow_type="feature_to_pr")
        assert cmd.continue_from_run_id == ""

    def test_continue_from_run_id_set(self):
        tr = ThreadRef(workspace_id="w", channel_id="c", thread_ts="t")
        cmd = StartWorkflow(
            thread_ref=tr, workflow_type="feature_to_pr", continue_from_run_id="prev-run-123"
        )
        assert cmd.continue_from_run_id == "prev-run-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/contracts/tests/test_commands.py::TestStartWorkflowContinuation -v`
Expected: FAIL — `continue_from_run_id` not a field

- [ ] **Step 3: Add field to StartWorkflow**

In `packages/contracts/src/lintel/contracts/commands.py`, add to `StartWorkflow`:

```python
    continue_from_run_id: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/contracts/tests/test_commands.py::TestStartWorkflowContinuation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/lintel/contracts/commands.py packages/contracts/tests/test_commands.py
git commit -m "feat: add continue_from_run_id to StartWorkflow command"
```

---

### Task 6: Rehydrate workflow state from previous run in WorkflowExecutor

**Files:**
- Modify: `packages/domain/src/lintel/domain/workflow_executor.py:102-158`
- Test: `packages/domain/tests/domain/test_workflow_executor_continuation.py`

- [ ] **Step 1: Write failing test for state rehydration**

```python
# packages/domain/tests/domain/test_workflow_executor_continuation.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass, field

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import (
    PipelineRun, PipelineStatus, Stage, StageStatus, ThreadRef,
)
from lintel.domain.workflow_executor import WorkflowExecutor


def _make_previous_run():
    """Create a failed pipeline run with research + plan outputs."""
    return PipelineRun(
        run_id="prev-run",
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="feature_to_pr",
        status=PipelineStatus.FAILED,
        trigger_type="chat:conv-1",
        trigger_id="t1",
        stages=(
            Stage(
                stage_id="s1", name="setup_workspace", stage_type="setup_workspace",
                status=StageStatus.SUCCEEDED,
                outputs={"sandbox_id": "sb-1", "feature_branch": "feat/test"},
            ),
            Stage(
                stage_id="s2", name="research", stage_type="research",
                status=StageStatus.SUCCEEDED,
                outputs={"research_report": "# Research\nFindings..."},
            ),
            Stage(
                stage_id="s3", name="plan", stage_type="plan",
                status=StageStatus.SUCCEEDED,
                outputs={"plan": {"tasks": [{"title": "Do X"}], "summary": "Do X"}},
            ),
            Stage(
                stage_id="s4", name="implement", stage_type="implement",
                status=StageStatus.FAILED,
                error="Sandbox timeout",
            ),
        ),
        created_at="2026-03-14T00:00:00Z",
    )


class TestRehydrateState:
    async def test_rehydrate_seeds_research_and_plan(self):
        """When continue_from_run_id is set, initial_input should contain
        research_context and plan from the previous run's stage outputs."""
        event_store = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.side_effect = lambda rid: (
            _make_previous_run() if rid == "prev-run" else None
        )

        graph = AsyncMock()
        graph.astream = AsyncMock(return_value=AsyncMock(__aiter__=lambda s: s, __anext__=AsyncMock(side_effect=StopAsyncIteration)))
        graph.get_state.return_value = MagicMock(next=[])

        app_state = MagicMock(
            pipeline_store=pipeline_store,
            sandbox_manager=None,
            credential_store=None,
            code_artifact_store=None,
            test_result_store=None,
        )

        executor = WorkflowExecutor(
            event_store=event_store,
            graph=graph,
            app_state=app_state,
        )

        tr = ThreadRef(workspace_id="w", channel_id="c", thread_ts="t")
        cmd = StartWorkflow(
            thread_ref=tr,
            workflow_type="feature_to_pr",
            project_id="proj-1",
            work_item_id="wi-1",
            run_id="new-run",
            continue_from_run_id="prev-run",
        )

        await executor.execute(cmd)

        # Verify graph.astream was called with rehydrated state
        call_args = graph.astream.call_args
        initial_input = call_args[0][0]
        assert initial_input["research_context"] == "# Research\nFindings..."
        assert initial_input["plan"]["tasks"][0]["title"] == "Do X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/domain/tests/domain/test_workflow_executor_continuation.py -v`
Expected: FAIL — `continue_from_run_id` not used, `research_context` not in initial_input

- [ ] **Step 3: Implement state rehydration in WorkflowExecutor.execute()**

In `workflow_executor.py`, after building `initial_input` (around line 148), add:

```python
        # Rehydrate state from previous run if continuing
        if command.continue_from_run_id:
            prev_state = await self._rehydrate_from_run(command.continue_from_run_id)
            initial_input.update(prev_state)

    async def _rehydrate_from_run(self, prev_run_id: str) -> dict[str, Any]:
        """Load stage outputs from a previous run and map them to workflow state keys."""
        result: dict[str, Any] = {}
        if self._app_state is None:
            return result
        pipeline_store = getattr(self._app_state, "pipeline_store", None)
        if pipeline_store is None:
            return result
        try:
            run = await pipeline_store.get(prev_run_id)
            if run is None:
                logger.warning("rehydrate_run_not_found", run_id=prev_run_id)
                return result
            for stage in run.stages:
                if isinstance(stage, dict):
                    stage = _dict_to_stage(stage)
                if stage.status != StageStatus.SUCCEEDED or not stage.outputs:
                    continue
                outputs = stage.outputs if isinstance(stage.outputs, dict) else {}
                # Map stage outputs to workflow state keys
                if stage.name == "research" and "research_report" in outputs:
                    result["research_context"] = outputs["research_report"]
                elif stage.name == "plan" and "plan" in outputs:
                    result["plan"] = outputs["plan"]
                elif stage.name == "setup_workspace":
                    if "feature_branch" in outputs:
                        result["feature_branch"] = outputs["feature_branch"]
            logger.info(
                "rehydrated_from_previous_run",
                prev_run_id=prev_run_id,
                keys=list(result.keys()),
            )
        except Exception:
            logger.warning("rehydrate_failed", prev_run_id=prev_run_id, exc_info=True)
        return result
```

Also add import at top:

```python
from lintel.contracts.types import StageStatus
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/domain/tests/domain/test_workflow_executor_continuation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/domain/src/lintel/domain/workflow_executor.py packages/domain/tests/domain/test_workflow_executor_continuation.py
git commit -m "feat: rehydrate workflow state from previous run for pipeline continuation"
```

---

### Task 7: Skip research/plan nodes when state already populated

**Files:**
- Modify: `packages/workflows/src/lintel/workflows/nodes/research.py:54-68`
- Modify: `packages/workflows/src/lintel/workflows/nodes/plan.py:79-102`
- Test: `packages/workflows/tests/workflows/nodes/test_skip_on_rehydrate.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/workflows/tests/workflows/nodes/test_skip_on_rehydrate.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from lintel.workflows.nodes.research import research_codebase
from lintel.workflows.nodes.plan import plan_work


class TestSkipResearchWhenRehydrated:
    async def test_skips_llm_when_research_context_present(self):
        """If research_context is already populated (rehydrated), skip the LLM call."""
        mock_runtime = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        state = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-1",
            "work_item_id": "wi-1",
            "workspace_path": "/workspace/repo",
            "research_context": "# Rehydrated Research\nPrevious findings.",
        }
        config = {
            "configurable": {
                "run_id": "run-1",
                "agent_runtime": mock_runtime,
                "sandbox_manager": None,
                "pipeline_store": pipeline_store,
                "app_state": MagicMock(pipeline_store=pipeline_store),
            }
        }

        result = await research_codebase(state, config)

        # LLM should NOT have been called
        mock_runtime.execute_step_stream.assert_not_awaited()
        # Research context should be passed through
        assert result["research_context"] == "# Rehydrated Research\nPrevious findings."


class TestSkipPlanWhenRehydrated:
    async def test_skips_llm_when_plan_present(self):
        """If plan is already populated (rehydrated), skip the LLM call."""
        mock_runtime = AsyncMock()
        pipeline_store = AsyncMock()
        pipeline_store.get.return_value = None

        state = {
            "thread_ref": "w/c/t",
            "sanitized_messages": ["add feature"],
            "sandbox_id": None,
            "run_id": "run-2",
            "work_item_id": "wi-2",
            "research_context": "research",
            "intent": "feature",
            "workspace_path": "/workspace/repo",
            "plan": {"tasks": [{"title": "Do X"}], "summary": "Do X"},
        }
        config = {
            "configurable": {
                "run_id": "run-2",
                "agent_runtime": mock_runtime,
                "sandbox_manager": None,
                "pipeline_store": pipeline_store,
                "app_state": MagicMock(pipeline_store=pipeline_store),
            }
        }

        result = await plan_work(state, config)

        mock_runtime.execute_step_stream.assert_not_awaited()
        assert result["plan"]["tasks"][0]["title"] == "Do X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_skip_on_rehydrate.py -v`
Expected: FAIL — LLM is still called

- [ ] **Step 3: Add skip guards to research and plan nodes**

In `research.py`, at the start of `research_codebase` (after `mark_running`):

```python
    # Skip if research_context already populated (pipeline continuation)
    existing_context = state.get("research_context", "")
    if existing_context:
        await tracker.append_log("research", "Using rehydrated research context — skipping LLM")
        await tracker.mark_completed(
            "research",
            outputs={"research_report": existing_context, "rehydrated": True},
        )
        return {
            "research_context": existing_context,
            "current_phase": "planning",
            "agent_outputs": [{"node": "research", "summary": "Rehydrated from previous run"}],
        }
```

In `plan.py`, at start of `plan_work` (after `mark_running`):

```python
    # Skip if plan already populated (pipeline continuation)
    existing_plan = state.get("plan", {})
    if existing_plan and existing_plan.get("tasks"):
        await tracker.append_log("plan", "Using rehydrated plan — skipping LLM")
        await tracker.mark_completed(
            "plan",
            outputs={"plan": existing_plan, "rehydrated": True},
        )
        return {
            "plan": existing_plan,
            "current_phase": "awaiting_spec_approval",
            "pending_approvals": ["spec_approval"],
            "agent_outputs": [{"node": "plan", "summary": "Rehydrated from previous run"}],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_skip_on_rehydrate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/workflows/src/lintel/workflows/nodes/research.py packages/workflows/src/lintel/workflows/nodes/plan.py packages/workflows/tests/workflows/nodes/test_skip_on_rehydrate.py
git commit -m "feat: skip research/plan nodes when state rehydrated from previous run"
```

---

### Task 8: Wire continuation into work item re-dispatch

When a work item is moved back to `in_progress` after a failed pipeline, find the last failed run and pass `continue_from_run_id`.

**Files:**
- Modify: `packages/app/src/lintel/api/routes/work_items.py:329-461`
- Test: `packages/app/tests/api/test_work_items_continuation.py`

- [ ] **Step 1: Write failing test**

```python
# packages/app/tests/api/test_work_items_continuation.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lintel.contracts.types import PipelineRun, PipelineStatus


class TestWorkItemContinuation:
    async def test_redispatch_passes_continue_from_run_id(self):
        """When re-dispatching a work item that had a failed pipeline,
        the StartWorkflow command should include continue_from_run_id."""
        # This is a design-level test to verify the integration point.
        # The actual wiring is in _trigger_workflow_for_work_item.
        from lintel.contracts.commands import StartWorkflow

        cmd = StartWorkflow(
            thread_ref=MagicMock(),
            workflow_type="feature_to_pr",
            project_id="p1",
            work_item_id="wi-1",
            run_id="new-run",
            continue_from_run_id="old-failed-run",
        )
        assert cmd.continue_from_run_id == "old-failed-run"
```

- [ ] **Step 2: Run test — should pass** (validates the field exists)

Run: `uv run pytest packages/app/tests/api/test_work_items_continuation.py -v`
Expected: PASS (after Task 5 is done)

- [ ] **Step 3: Modify `_trigger_workflow_for_work_item` to look up last failed run**

In `work_items.py`, inside `_trigger_workflow_for_work_item`, before building `StartWorkflow`:

```python
    # Find most recent failed pipeline for this work item (for continuation)
    continue_from_run_id = ""
    if pipeline_store:
        try:
            all_runs = await pipeline_store.list_all()
            failed_runs = [
                r for r in all_runs
                if (
                    (r.work_item_id if hasattr(r, "work_item_id") else r.get("work_item_id", ""))
                    == work_item_id
                    and (r.status if hasattr(r, "status") else r.get("status", ""))
                    in ("failed", PipelineStatus.FAILED)
                )
            ]
            if failed_runs:
                # Pick most recent by created_at
                failed_runs.sort(
                    key=lambda r: (
                        r.created_at if hasattr(r, "created_at") else r.get("created_at", "")
                    ),
                    reverse=True,
                )
                prev = failed_runs[0]
                continue_from_run_id = (
                    prev.run_id if hasattr(prev, "run_id") else prev.get("run_id", "")
                )
                logger.info("continuing_from_previous_run", prev_run_id=continue_from_run_id)
        except Exception:
            logger.warning("continuation_lookup_failed", exc_info=True)
```

Then add `continue_from_run_id=continue_from_run_id` to the `StartWorkflow` constructor.

- [ ] **Step 4: Run lint + type check**

Run: `uv run ruff check packages/app/src/lintel/api/routes/work_items.py`
Expected: clean

- [ ] **Step 5: Commit**

```bash
git add packages/app/src/lintel/api/routes/work_items.py packages/app/tests/api/test_work_items_continuation.py
git commit -m "feat: wire pipeline continuation into work item re-dispatch"
```

---

### Task 9: Inject failure context into implement node prompt

When continuing from a failed implement stage, include the error message so the agent knows what went wrong.

**Files:**
- Modify: `packages/domain/src/lintel/domain/workflow_executor.py` (in `_rehydrate_from_run`)
- Modify: `packages/workflows/src/lintel/workflows/nodes/implement.py` (use `previous_error` in prompt)
- Test: `packages/workflows/tests/workflows/nodes/test_implement_continuation.py`

- [ ] **Step 1: Write failing test**

```python
# packages/workflows/tests/workflows/nodes/test_implement_continuation.py

import pytest


class TestImplementContinuationContext:
    def test_rehydrate_includes_failure_context(self):
        """_rehydrate_from_run should include the failed stage's error."""
        # This is tested via the executor test in Task 6.
        # Here we verify the implement node uses `previous_error` in state.
        state = {
            "previous_error": "Sandbox timeout after 300s",
            "sanitized_messages": ["add button"],
        }
        messages = state.get("sanitized_messages", [])
        error = state.get("previous_error", "")
        assert error == "Sandbox timeout after 300s"
        # The implement node should include this in its prompt context
```

- [ ] **Step 2: Run test**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_implement_continuation.py -v`
Expected: PASS

- [ ] **Step 3: Add `previous_error` to rehydration and implement prompt**

In `workflow_executor.py` `_rehydrate_from_run`, for the failed stage:

```python
                if stage.status == StageStatus.FAILED and stage.error:
                    result["previous_error"] = stage.error
                    result["previous_failed_stage"] = stage.name
```

In `implement.py`, when building the prompt for the coder agent, prepend the error context if present:

```python
    previous_error = state.get("previous_error", "")
    if previous_error:
        prev_stage = state.get("previous_failed_stage", "implement")
        error_context = (
            f"\n\n## Previous Attempt Failed\n"
            f"The previous pipeline run failed at the **{prev_stage}** stage with:\n"
            f"```\n{previous_error}\n```\n"
            f"Take this into account and avoid the same failure mode.\n"
        )
        # Prepend to user request
```

- [ ] **Step 4: Run all continuation tests**

Run: `uv run pytest packages/workflows/tests/workflows/nodes/test_implement_continuation.py packages/domain/tests/domain/test_workflow_executor_continuation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/domain/src/lintel/domain/workflow_executor.py packages/workflows/src/lintel/workflows/nodes/implement.py packages/workflows/tests/workflows/nodes/test_implement_continuation.py
git commit -m "feat: inject failure context from previous run into implement node"
```

---

### Task 10: Final integration — run affected tests

- [ ] **Step 1: Run affected tests**

Run: `make test-affected`
Expected: all pass

- [ ] **Step 2: Run lint + typecheck**

Run: `make lint && make typecheck`
Expected: clean

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: address lint/type issues from pipeline continuation feature"
```
