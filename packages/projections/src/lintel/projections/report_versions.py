"""Report version projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


@dataclass
class VersionSummary:
    """Summary of a single report version."""

    version: int
    editor: str
    edited_at: str
    event_type: str


@dataclass
class ReportVersionEntry:
    """Read model for a (run_id, stage_id) pair."""

    run_id: str
    stage_id: str
    latest_version: int = 0
    edit_count: int = 0
    last_editor: str = ""
    versions: list[VersionSummary] = field(default_factory=list)


class ReportVersionProjection:
    """Maintains an in-memory report version view per (run_id, stage_id)."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "StageReportEdited",
            "StageReportRegenerated",
        }
    )

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "report_versions"

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    def _key(self, run_id: str, stage_id: str) -> str:
        return f"{run_id}:{stage_id}"

    async def project(self, event: EventEnvelope) -> None:
        payload = event.payload
        run_id = str(payload.get("run_id", ""))
        stage_id = str(payload.get("stage_id", ""))
        key = self._key(run_id, stage_id)

        current = self._state.get(key)
        if current is None:
            entry = ReportVersionEntry(run_id=run_id, stage_id=stage_id)
            current = asdict(entry)

        new_version = current.get("latest_version", 0) + 1
        current["latest_version"] = new_version
        current["edit_count"] = current.get("edit_count", 0) + 1
        current["last_editor"] = event.actor_id

        summary = VersionSummary(
            version=new_version,
            editor=event.actor_id,
            edited_at=event.occurred_at.isoformat(),
            event_type=event.event_type,
        )
        versions = current.get("versions", [])
        versions.append(asdict(summary))
        current["versions"] = versions

        self._state[key] = current

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._state.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    def get_latest(self, run_id: str, stage_id: str) -> int:
        """Return the latest version number for the given run/stage, or 0."""
        key = self._key(run_id, stage_id)
        entry = self._state.get(key)
        if entry is None:
            return 0
        return int(entry.get("latest_version", 0))

    def get_history(self, run_id: str, stage_id: str) -> list[dict[str, Any]]:
        """Return the list of version summaries for the given run/stage."""
        key = self._key(run_id, stage_id)
        entry = self._state.get(key)
        if entry is None:
            return []
        return list(entry.get("versions", []))

    def get_edit_count(self, run_id: str, stage_id: str) -> int:
        """Return the total edit count for the given run/stage, or 0."""
        key = self._key(run_id, stage_id)
        entry = self._state.get(key)
        if entry is None:
            return 0
        return int(entry.get("edit_count", 0))
