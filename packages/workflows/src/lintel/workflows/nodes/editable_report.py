"""EditableReportNode — human-editable report gate (F013).

Pauses the workflow and presents a markdown report for human editing.
Resume input should be a string (edited markdown) or a dict with
``{"content": "...edited markdown..."}``.
"""

from __future__ import annotations

from typing import Any, Literal

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.types import InterruptType

# Node type discriminator for the REQ-020 node registry
NODE_TYPE = "editable_report"


class EditableReportNode(HumanInterruptNode):
    """Blocks the pipeline until a human edits and confirms a report."""

    def __init__(
        self,
        node_name: str = "editable_report",
        *,
        report_state_key: str = "research_context",
        timeout: int = 0,
        on_timeout_action: Literal["auto_proceed", "auto_escalate"] = "auto_proceed",
        channel_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(node_name, channel_config=channel_config)
        self._report_state_key = report_state_key
        self._timeout = timeout
        self._on_timeout = on_timeout_action

    @property
    def interrupt_type(self) -> InterruptType:
        return InterruptType.EDITABLE_REPORT

    @property
    def timeout_seconds(self) -> int:
        return self._timeout

    @property
    def on_timeout(self) -> Literal["auto_proceed", "auto_escalate"]:
        return self._on_timeout

    def _build_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = super()._build_payload(state)
        payload["report_content"] = state.get(self._report_state_key, "")
        payload["report_state_key"] = self._report_state_key
        return payload

    async def process_resume(
        self,
        state: dict[str, Any],
        human_input: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        """Accept edited report and update the corresponding state field."""
        if isinstance(human_input, dict):
            content = human_input.get("content", "")
        elif isinstance(human_input, str):
            content = human_input
        else:
            content = str(human_input)

        return {
            self._report_state_key: content,
            "current_phase": state.get("current_phase", ""),
            "agent_outputs": [
                {
                    "node": self.node_name,
                    "output": "Report edited and confirmed by human",
                }
            ],
        }
