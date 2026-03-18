"""Workflow node implementations.

Exports the shared HumanInterruptNode base and its subclasses
(EditableReportNode, HumanTaskNode) for human-in-the-loop interrupt/resume
workflows, plus the legacy ApprovalGateNode (interrupt_before-based gate).
"""

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.nodes.human_task import HumanTaskNode

__all__ = [
    "ApprovalGateNode",
    "EditableReportNode",
    "HumanInterruptNode",
    "HumanTaskNode",
]


def __getattr__(name: str) -> object:
    """Lazy imports to avoid circular dependencies at module load time."""
    if name == "ApprovalGateNode":
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        return ApprovalGateNode
    if name == "EditableReportNode":
        from lintel.workflows.nodes.editable_report import EditableReportNode

        return EditableReportNode
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
