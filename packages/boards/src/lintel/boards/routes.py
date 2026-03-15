"""Board and Tag CRUD endpoints for the internal task board."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    BoardCreated,
    BoardRemoved,
    BoardUpdated,
    TagCreated,
    TagRemoved,
    TagUpdated,
)

if TYPE_CHECKING:
    from lintel.boards.store import BoardStore, TagStore

router = APIRouter()

tag_store_provider = StoreProvider()
board_store_provider = StoreProvider()


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
    auto_move: bool = False


class UpdateBoardRequest(BaseModel):
    name: str | None = None
    columns: list[BoardColumnRequest] | None = None
    auto_move: bool | None = None


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------


@router.post("/tags", status_code=201)
async def create_tag(
    body: CreateTagRequest,
    request: Request,
    store: TagStore = Depends(tag_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.tag_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tag already exists")
    data = body.model_dump()
    await store.add(data)
    await dispatch_event(
        request,
        TagCreated(payload={"resource_id": body.tag_id, "name": body.name}),
        stream_id=f"tag:{body.tag_id}",
    )
    result = await store.get(body.tag_id)
    return result  # type: ignore[return-value]


@router.get("/projects/{project_id}/tags")
async def list_tags(
    project_id: str,
    store: TagStore = Depends(tag_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_by_project(project_id)


@router.get("/tags/{tag_id}")
async def get_tag(
    tag_id: str,
    store: TagStore = Depends(tag_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return item


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: str,
    body: UpdateTagRequest,
    request: Request,
    store: TagStore = Depends(tag_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(tag_id, merged)
    await dispatch_event(
        request,
        TagUpdated(payload={"resource_id": tag_id, "fields": list(updates.keys())}),
        stream_id=f"tag:{tag_id}",
    )
    result = await store.get(tag_id)
    return result  # type: ignore[return-value]


@router.delete("/tags/{tag_id}", status_code=204)
async def remove_tag(
    tag_id: str,
    request: Request,
    store: TagStore = Depends(tag_store_provider),  # noqa: B008
) -> None:
    item = await store.get(tag_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    await store.remove(tag_id)
    await dispatch_event(
        request,
        TagRemoved(payload={"resource_id": tag_id, "name": item.get("name", "")}),
        stream_id=f"tag:{tag_id}",
    )


# ---------------------------------------------------------------------------
# Board endpoints
# ---------------------------------------------------------------------------


@router.post("/boards", status_code=201)
async def create_board(
    body: CreateBoardRequest,
    request: Request,
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.board_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Board already exists")
    data = body.model_dump()
    await store.add(data)
    await dispatch_event(
        request,
        BoardCreated(payload={"resource_id": body.board_id, "name": body.name}),
        stream_id=f"board:{body.board_id}",
    )
    result = await store.get(body.board_id)
    return result  # type: ignore[return-value]


@router.get("/projects/{project_id}/boards")
async def list_boards(
    project_id: str,
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_by_project(project_id)


@router.get("/boards/{board_id}")
async def get_board(
    board_id: str,
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return item


@router.patch("/boards/{board_id}")
async def update_board(
    board_id: str,
    body: UpdateBoardRequest,
    request: Request,
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(board_id, merged)
    await dispatch_event(
        request,
        BoardUpdated(payload={"resource_id": board_id, "fields": list(updates.keys())}),
        stream_id=f"board:{board_id}",
    )
    result = await store.get(board_id)
    return result  # type: ignore[return-value]


@router.delete("/boards/{board_id}", status_code=204)
async def remove_board(
    board_id: str,
    request: Request,
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> None:
    item = await store.get(board_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Board not found")
    await store.remove(board_id)
    await dispatch_event(
        request,
        BoardRemoved(payload={"resource_id": board_id, "name": item.get("name", "")}),
        stream_id=f"board:{board_id}",
    )
