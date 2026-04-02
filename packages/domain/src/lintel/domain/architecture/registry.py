"""ADR registry for managing architecture decisions."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from lintel.domain.architecture.types import ADRStatus, ArchitectureDecision, ArchitectureLayer


class ADRRegistry:
    """In-memory registry for architecture decision records."""

    def __init__(self) -> None:
        self._decisions: dict[str, ArchitectureDecision] = {}
        self._layers: dict[str, ArchitectureLayer] = {}

    def propose(
        self,
        title: str,
        context: str,
        decision: str,
        alternatives: tuple[str, ...] = (),
        *,
        author: str = "",
    ) -> ArchitectureDecision:
        """Create a new proposed ADR."""
        adr_id = str(uuid.uuid4())
        adr = ArchitectureDecision(
            adr_id=adr_id,
            title=title,
            context=context,
            decision=decision,
            alternatives=alternatives,
            author=author,
            created_at=datetime.now(tz=UTC),
        )
        self._decisions[adr_id] = adr
        return adr

    def accept(self, adr_id: str) -> ArchitectureDecision:
        """Accept a proposed ADR."""
        adr = self._get_or_raise(adr_id)
        updated = ArchitectureDecision(
            adr_id=adr.adr_id,
            title=adr.title,
            status=ADRStatus.ACCEPTED,
            context=adr.context,
            decision=adr.decision,
            consequences=adr.consequences,
            alternatives=adr.alternatives,
            author=adr.author,
            created_at=adr.created_at,
            superseded_by=adr.superseded_by,
        )
        self._decisions[adr_id] = updated
        return updated

    def deprecate(self, adr_id: str, reason: str) -> ArchitectureDecision:
        """Deprecate an ADR with a reason stored in consequences."""
        adr = self._get_or_raise(adr_id)
        updated = ArchitectureDecision(
            adr_id=adr.adr_id,
            title=adr.title,
            status=ADRStatus.DEPRECATED,
            context=adr.context,
            decision=adr.decision,
            consequences=reason,
            alternatives=adr.alternatives,
            author=adr.author,
            created_at=adr.created_at,
            superseded_by=adr.superseded_by,
        )
        self._decisions[adr_id] = updated
        return updated

    def supersede(self, adr_id: str, new_adr_id: str) -> ArchitectureDecision:
        """Mark an ADR as superseded by another."""
        adr = self._get_or_raise(adr_id)
        self._get_or_raise(new_adr_id)  # ensure new ADR exists
        updated = ArchitectureDecision(
            adr_id=adr.adr_id,
            title=adr.title,
            status=ADRStatus.SUPERSEDED,
            context=adr.context,
            decision=adr.decision,
            consequences=adr.consequences,
            alternatives=adr.alternatives,
            author=adr.author,
            created_at=adr.created_at,
            superseded_by=new_adr_id,
        )
        self._decisions[adr_id] = updated
        return updated

    def get(self, adr_id: str) -> ArchitectureDecision | None:
        """Get an ADR by ID, or None if not found."""
        return self._decisions.get(adr_id)

    def list(self, status_filter: ADRStatus | None = None) -> list[ArchitectureDecision]:
        """List all ADRs, optionally filtered by status."""
        adrs = list(self._decisions.values())
        if status_filter is not None:
            adrs = [a for a in adrs if a.status == status_filter]
        return adrs

    def search(self, query: str) -> list[ArchitectureDecision]:
        """Search ADRs by title or context (case-insensitive substring match)."""
        q = query.lower()
        return [
            a for a in self._decisions.values() if q in a.title.lower() or q in a.context.lower()
        ]

    def add_layer(self, layer: ArchitectureLayer) -> None:
        """Register an architecture layer."""
        self._layers[layer.layer_name] = layer

    def get_layer(self, layer_name: str) -> ArchitectureLayer | None:
        """Get an architecture layer by name."""
        return self._layers.get(layer_name)

    def _get_or_raise(self, adr_id: str) -> ArchitectureDecision:
        adr = self._decisions.get(adr_id)
        if adr is None:
            msg = f"ADR {adr_id} not found"
            raise KeyError(msg)
        return adr
