"""Release notes CRUD endpoints."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.release_notes_api.store import InMemoryReleaseNoteStore
from lintel.release_notes_api.types import ReleaseEntry, ReleaseNote

router = APIRouter()

release_note_store_provider: StoreProvider[InMemoryReleaseNoteStore] = StoreProvider()


class ReleaseEntryRequest(BaseModel):
    pr_number: int
    title: str
    category: str
    description: str


class CreateReleaseNoteRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    version: str
    title: str
    summary: str
    entries: list[ReleaseEntryRequest] = []


class UpdateReleaseNoteRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    version: str | None = None
    entries: list[ReleaseEntryRequest] | None = None
    published_at: str | None = None


def _note_to_dict(note: ReleaseNote) -> dict[str, Any]:
    data = asdict(note)
    data["entries"] = [asdict(e) for e in note.entries]
    return data


@router.post("/release-notes", status_code=201)
async def create_release_note(
    body: CreateReleaseNoteRequest,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Release note already exists")
    note = ReleaseNote(
        id=body.id,
        project_id=body.project_id,
        version=body.version,
        title=body.title,
        summary=body.summary,
        entries=tuple(
            ReleaseEntry(
                pr_number=e.pr_number,
                title=e.title,
                category=e.category,
                description=e.description,
            )
            for e in body.entries
        ),
        generated_at=datetime.now(UTC).isoformat(),
    )
    await store.add(note)
    return _note_to_dict(note)


@router.get("/release-notes")
async def list_release_notes(
    project_id: str | None = None,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    if project_id:
        notes = await store.list_by_project(project_id)
    else:
        notes = await store.list_all()
    return [_note_to_dict(n) for n in notes]


@router.get("/release-notes/{note_id}")
async def get_release_note(
    note_id: str,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
) -> dict[str, Any]:
    note = await store.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Release note not found")
    return _note_to_dict(note)


@router.patch("/release-notes/{note_id}")
async def update_release_note(
    note_id: str,
    body: UpdateReleaseNoteRequest,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
) -> dict[str, Any]:
    note = await store.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Release note not found")
    updates: dict[str, Any] = body.model_dump(exclude_none=True)
    if "entries" in updates:
        updates["entries"] = tuple(
            ReleaseEntry(
                pr_number=e["pr_number"],
                title=e["title"],
                category=e["category"],
                description=e["description"],
            )
            for e in updates["entries"]
        )
    current = asdict(note)
    current["entries"] = note.entries  # keep as tuple, not list-of-dicts
    current.update(updates)
    updated = ReleaseNote(**current)
    await store.update(updated)
    return _note_to_dict(updated)


@router.delete("/release-notes/{note_id}", status_code=204)
async def delete_release_note(
    note_id: str,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
) -> None:
    note = await store.get(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Release note not found")
    await store.remove(note_id)
