"""Board and Tag CRUD endpoints for the internal task board."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.contracts.data_models import BoardData, TagData

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------


class TagStore:
    """In-memory tag store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        validated = TagData.model_validate(data)
        self._data[validated.tag_id] = validated.model_dump()

    async def get(self, tag_id: str) -> dict[str, Any] | None:
        return self._data.get(tag_id)

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [t for t in self._data.values() if t.get("project_id") == project_id]

    async def update(self, tag_id: str, data: dict[str, Any]) -> None:
        validated = TagData.model_validate(data)
        self._data[tag_id] = validated.model_dump()

    async def remove(self, tag_id: str) -> None:
        self._data.pop(tag_id, None)


class BoardStore:
    """In-memory board store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        validated = BoardData.model_validate(data)
        self._data[validated.board_id] = validated.model_dump()

    async def get(self, board_id: str) -> dict[str, Any] | None:
        return self._data.get(board_id)

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [b for b in self._data.values() if b.get("project_id") == project_id]

    async def update(self, board_id: str, data: dict[str, Any]) -> None:
        validated = BoardData.model_validate(data)
        self._data[board_id] = validated.model_dump()

    async def remove(self, board_id: str) -> None:
        self._data.pop(board_id, None)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_tag_store(request: Request) -> TagStore:
    return request.app.state.tag_store  # type: ignore[no-any-return]


def get_board_store(request: Request) -> BoardStore:
    return request.app.state.board_store  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTagRequest(BaseModel):
    tag_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    color: str = "#6b7280"


class UpdateTagRequest(BaseModel):
    name: str | None = None
    color: str | None = None


class BoardColumnRequest(BaseModel):
    column_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    position: int = 0
    work_item_status: str = ""
    wip_limit: int = 0  # 0 = unlimited


class CreateBoardRequest(BaseModel):
    board_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    columns: list[BoardColumnRequest] = Field(default_factory=list)


class UpdateBoardRequest(BaseModel):
    name: str | None = None
    columns: list[BoardColumnRequest] | None = None


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------


@router.post("/tags", status_code=201)
async def create_tag(
    body: CreateTagRequest,
    store: Annotated[TagStore, Depends(get_tag_store)],
) -> dict[str, Any]:
    existing = await store.get(body.tag_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tag already exists")
    data = body.model_dump()
    await store.add(data)
    result = await store.get(body.tag_id)
    return result  # type: ignore[return-value]


@router.get("/projects/{project_id}/tags")
async def list_tags(
    project_id: str,
    store: Annotated[TagStore, Depends(get_tag_store)],
) -> list[dict[str, Any]]:
    return await store.list_by_project(project_id)


@router.get("/tags/{tag_id}")
async def get_tag(
    tag_id: str,
    store: Annotated[TagStore, Depends(get_tag_store)],
) -> dict[str, Any]:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return item


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: str,
    body: UpdateTagRequest,
    store: Annotated[TagStore, Depends(get_tag_store)],
) -> dict[str, Any]:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(tag_id, merged)
    result = await store.get(tag_id)
    return result  # type: ignore[return-value]


@router.delete("/tags/{tag_id}", status_code=204)
async def remove_tag(
    tag_id: str,
    store: Annotated[TagStore, Depends(get_tag_store)],
) -> None:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    await store.remove(tag_id)


# ---------------------------------------------------------------------------
# Board endpoints
# ---------------------------------------------------------------------------


@router.post("/boards", status_code=201)
async def create_board(
    body: CreateBoardRequest,
    store: Annotated[BoardStore, Depends(get_board_store)],
) -> dict[str, Any]:
    existing = await store.get(body.board_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Board already exists")
    data = body.model_dump()
    await store.add(data)
    result = await store.get(body.board_id)
    return result  # type: ignore[return-value]


@router.get("/projects/{project_id}/boards")
async def list_boards(
    project_id: str,
    store: Annotated[BoardStore, Depends(get_board_store)],
) -> list[dict[str, Any]]:
    return await store.list_by_project(project_id)


@router.get("/boards/{board_id}")
async def get_board(
    board_id: str,
    store: Annotated[BoardStore, Depends(get_board_store)],
) -> dict[str, Any]:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return item


@router.patch("/boards/{board_id}")
async def update_board(
    board_id: str,
    body: UpdateBoardRequest,
    store: Annotated[BoardStore, Depends(get_board_store)],
) -> dict[str, Any]:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(board_id, merged)
    result = await store.get(board_id)
    return result  # type: ignore[return-value]


@router.delete("/boards/{board_id}", status_code=204)
async def remove_board(
    board_id: str,
    store: Annotated[BoardStore, Depends(get_board_store)],
) -> None:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    await store.remove(board_id)
