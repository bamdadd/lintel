"""Release notes CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import re
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.release_notes_api.types import ReleaseEntry, ReleaseNote

if TYPE_CHECKING:
    from lintel.release_notes_api.store import InMemoryReleaseNoteStore

router = APIRouter()

release_note_store_provider: StoreProvider[InMemoryReleaseNoteStore] = StoreProvider()
repo_provider_provider: StoreProvider[Any] = StoreProvider()


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


# ---------------------------------------------------------------------------
# Generate release notes from merged PRs
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("feature", re.compile(r"^feat[\(:]", re.IGNORECASE)),
    ("bugfix", re.compile(r"^fix[\(:]", re.IGNORECASE)),
    ("chore", re.compile(r"^chore[\(:]", re.IGNORECASE)),
    ("docs", re.compile(r"^docs[\(:]", re.IGNORECASE)),
    ("refactor", re.compile(r"^refactor[\(:]", re.IGNORECASE)),
    ("test", re.compile(r"^test[\(:]", re.IGNORECASE)),
    ("ci", re.compile(r"^ci[\(:]", re.IGNORECASE)),
    ("perf", re.compile(r"^perf[\(:]", re.IGNORECASE)),
]


def _categorise_pr(title: str) -> str:
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(title):
            return category
    return "other"


class GenerateReleaseNoteRequest(BaseModel):
    project_id: str
    repo_url: str
    version: str
    title: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


@router.post("/release-notes/generate", status_code=201)
async def generate_release_note(
    body: GenerateReleaseNoteRequest,
    store: InMemoryReleaseNoteStore = Depends(release_note_store_provider),  # noqa: B008
    provider: Any = Depends(repo_provider_provider),  # noqa: B008, ANN401
) -> dict[str, Any]:
    prs: list[dict[str, Any]] = await provider.list_pull_requests(
        body.repo_url, state="closed", limit=body.limit
    )
    if not prs:
        raise HTTPException(status_code=422, detail="No closed PRs found for repository")

    entries = tuple(
        ReleaseEntry(
            pr_number=pr["number"],
            title=pr["title"],
            category=_categorise_pr(pr["title"]),
            description=pr["title"],
        )
        for pr in prs
    )

    categories = {e.category for e in entries}
    summary_parts: list[str] = []
    for cat in sorted(categories):
        count = sum(1 for e in entries if e.category == cat)
        summary_parts.append(f"{count} {cat}")
    summary = ", ".join(summary_parts)

    note = ReleaseNote(
        id=str(uuid4()),
        project_id=body.project_id,
        version=body.version,
        title=body.title or f"Release {body.version}",
        summary=summary,
        entries=entries,
        generated_at=datetime.now(UTC).isoformat(),
    )
    await store.add(note)
    return _note_to_dict(note)
