"""Workflow node implementations.

Exports the shared HumanInterruptNode base and its subclasses
<<<<<<< Updated upstream
(EditableReportNode, HumanTaskNode, ApprovalGateNode) for human-in-the-loop
=======
(ApprovalGateNode, EditableReportNode, HumanTaskNode) for human-in-the-loop
>>>>>>> Stashed changes
interrupt/resume workflows.
"""

from lintel.workflows.nodes.human_interrupt import HumanInterruptNode
from lintel.workflows.nodes.human_task import HumanTaskNode

__all__ = [
    "ApprovalGateNode",
    "EditableReportNode",
    "HumanInterruptNode",
    "HumanTaskNode",
    "NodeRejectedError",
]


def __getattr__(name: str) -> object:
    """Lazy imports to avoid circular dependencies at module load time."""
    if name == "ApprovalGateNode":
        from lintel.workflows.nodes.approval_gate import ApprovalGateNode

        return ApprovalGateNode
    if name == "NodeRejectedError":
        from lintel.workflows.nodes.approval_gate import NodeRejectedError

        return NodeRejectedError
    if name == "EditableReportNode":
        from lintel.workflows.nodes.editable_report import EditableReportNode

        return EditableReportNode
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
