"""In-memory audit entry store."""

from lintel.domain.types import AuditEntry


class AuditEntryStore:
    """In-memory append-only store for audit entries."""

    def __init__(self) -> None:
        self._entries: dict[str, AuditEntry] = {}

    async def add(self, entry: AuditEntry) -> None:
        self._entries[entry.entry_id] = entry

    async def get(self, entry_id: str) -> AuditEntry | None:
        return self._entries.get(entry_id)

    async def list_all(
        self,
        *,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> list[AuditEntry]:
        entries = list(self._entries.values())
        if actor_id is not None:
            entries = [e for e in entries if e.actor_id == actor_id]
        if resource_type is not None:
            entries = [e for e in entries if e.resource_type == resource_type]
        if resource_id is not None:
            entries = [e for e in entries if e.resource_id == resource_id]
        return entries
