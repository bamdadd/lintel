"""In-memory release notes store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.release_notes_api.types import ReleaseNote


class InMemoryReleaseNoteStore:
    """Simple in-memory store for release notes."""

    def __init__(self) -> None:
        self._notes: dict[str, ReleaseNote] = {}

    async def add(self, note: ReleaseNote) -> None:
        self._notes[note.id] = note

    async def get(self, note_id: str) -> ReleaseNote | None:
        return self._notes.get(note_id)

    async def list_all(self) -> list[ReleaseNote]:
        return list(self._notes.values())

    async def list_by_project(self, project_id: str) -> list[ReleaseNote]:
        return [n for n in self._notes.values() if n.project_id == project_id]

    async def update(self, note: ReleaseNote) -> None:
        self._notes[note.id] = note

    async def remove(self, note_id: str) -> None:
        del self._notes[note_id]
