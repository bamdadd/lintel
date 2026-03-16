"""HumanTaskNode — open-ended human task input (F018).

Pauses the workflow for a human to provide open-ended input.
Resume input is an arbitrary dict that gets merged into state.
"""

from __future__ import annotations

from typing import Any, Literal

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.types import InterruptType

# Node type discriminator for the REQ-020 node registry
NODE_TYPE = "human_task"


class HumanTaskNode(HumanInterruptNode):
    """Blocks the pipeline for an open-ended human task."""

    def __init__(
        self,
        node_name: str = "human_task",
        *,
        task_description: str = "",
        timeout: int = 0,
        on_timeout_action: Literal["auto_proceed", "auto_escalate"] = "auto_escalate",
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_name, channel_config=channel_config)
        self._task_description = task_description
        self._timeout = timeout
        self._on_timeout = on_timeout_action

    @property
    def interrupt_type(self) -> InterruptType:
        return InterruptType.HUMAN_TASK

    @property
    def timeout_seconds(self) -> int:
        return self._timeout

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return self._on_timeout

    def _build_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = super()._build_payload(state)
        payload["task_description"] = self._task_description
        return payload

    def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Merge human-provided dict into state."""
        result: dict[str, Any] = {
            "current_phase": state.get("current_phase", ""),
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": "Human task completed",
                }
            ],
        }

        if isinstance(human_input, dict):
            # Merge human input fields into state update, excluding
            # internal fields that shouldn't be overwritten.
            protected = {"run_id", "correlation_id", "thread_ref"}
            for key, value in human_input.items():
                if key not in protected:
                    result[key] = value

        return result
