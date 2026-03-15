"""In-memory approval request store."""

from lintel.domain.types import ApprovalRequest


class InMemoryApprovalRequestStore:
    """Simple in-memory store for approval requests."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    async def add(self, approval: ApprovalRequest) -> None:
        if approval.approval_id in self._requests:
            msg = f"ApprovalRequest {approval.approval_id} already exists"
            raise ValueError(msg)
        self._requests[approval.approval_id] = approval

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    async def list_all(self) -> list[ApprovalRequest]:
        return list(self._requests.values())

    async def update(self, approval: ApprovalRequest) -> None:
        if approval.approval_id not in self._requests:
            msg = f"ApprovalRequest {approval.approval_id} not found"
            raise KeyError(msg)
        self._requests[approval.approval_id] = approval
