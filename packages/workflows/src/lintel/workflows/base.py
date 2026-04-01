"""WorkflowNode base class for LangGraph-compatible workflow nodes.

Provides common boilerplate: StageTracker initialisation, mark_running/mark_completed
lifecycle, and error handling. Subclasses implement ``execute()`` with the domain logic.

Usage::

    class MyNode(WorkflowNode):
        name: str = "my_stage"

        async def execute(
            self, state: ThreadWorkflowState, config: RunnableConfig,
        ) -> dict[str, Any]:
            await self.tracker.append_log(self.name, "Working...")
            return {"current_phase": "done"}

    # Register in LangGraph graph:
    graph.add_node("my_stage", MyNode())
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict
import structlog

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.nodes._stage_tracking import StageTracker
    from lintel.workflows.state import ThreadWorkflowState

logger = structlog.get_logger()


class WorkflowNode(BaseModel, abc.ABC):
    """Base class for Pydantic-based LangGraph workflow nodes.

    Subclasses MUST set ``name`` and implement ``execute()``.
    The ``__call__`` method makes instances directly usable as LangGraph node functions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    """Stage name used for StageTracker (must match NODE_TO_STAGE keys)."""

    # Set during __call__; not part of the model schema.
    _tracker: StageTracker | None = None
    _completed: bool = False

    @property
    def tracker(self) -> StageTracker:
        """Access the StageTracker initialised by ``__call__``.

        Only valid inside ``execute()``; raises if accessed outside a call.
        """
        if self._tracker is None:
            msg = "StageTracker is only available inside execute()"
            raise RuntimeError(msg)
        return self._tracker

    async def complete(
        self,
        outputs: dict[str, object] | None = None,
        error: str = "",
    ) -> None:
        """Mark the stage as completed with optional outputs.

        Call this from ``execute()`` when you need to attach stage outputs.
        If not called, the base ``__call__`` will auto-complete the stage.
        """
        object.__setattr__(self, "_completed", True)
        await self.tracker.mark_completed(self.name, outputs=outputs, error=error)

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def execute(
        self,
        state: ThreadWorkflowState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Implement the node's domain logic.

        ``self.tracker`` is already initialised and ``mark_running`` has been called.
        The returned dict is merged into the LangGraph state.

        Call ``await self.tracker.mark_completed(self.name, outputs=...)`` when you
        want to attach stage outputs.  If you do not call ``mark_completed`` yourself,
        the base class calls it automatically on successful return.
        """

    # ------------------------------------------------------------------
    # LangGraph entry-point
    # ------------------------------------------------------------------

    async def __call__(
        self,
        state: ThreadWorkflowState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """LangGraph-compatible entry-point.

        1. Initialises a ``StageTracker`` and marks the stage as running.
        2. Delegates to ``execute()``.
        3. Marks the stage as completed (or failed on exception).
        """
        from lintel.workflows.nodes._stage_tracking import StageTracker

        tracker = StageTracker(config, state)
        # Store via object.__setattr__ to bypass Pydantic frozen/private-field machinery.
        object.__setattr__(self, "_tracker", tracker)

        object.__setattr__(self, "_completed", False)

        try:
            await tracker.mark_running(self.name)
            result = await self.execute(state, config)
            if not self._completed:
                await tracker.mark_completed(self.name)
            return result
        except Exception as exc:
            logger.exception("workflow_node_failed", node=self.name, error=str(exc))
            if not self._completed:
                await tracker.mark_completed(self.name, error=str(exc))
            return {
                "current_phase": "failed",
                "error": str(exc),
            }
        finally:
            object.__setattr__(self, "_tracker", None)
            object.__setattr__(self, "_completed", False)
