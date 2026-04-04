"""Board and Tag CRUD endpoints for the internal task board."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
    from lintel.work_items_api.store import WorkItemStore

router = APIRouter()

tag_store_provider: StoreProvider[TagStore] = StoreProvider()
board_store_provider: StoreProvider[BoardStore] = StoreProvider()
work_item_store_provider: StoreProvider[WorkItemStore] = StoreProvider()


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
    work_item_statuses: list[str] = Field(default_factory=list)
    work_item_status: str = ""  # deprecated — use work_item_statuses
    wip_limit: int = 0  # 0 = unlimited

    def resolved_statuses(self) -> tuple[str, ...]:
        """Return statuses, falling back to single work_item_status for compat."""
        if self.work_item_statuses:
            return tuple(s for s in self.work_item_statuses if s)
        if self.work_item_status:
            return (self.work_item_status,)
        return ()


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


def _normalize_column(col_dict: dict[str, Any], col_req: BoardColumnRequest) -> dict[str, Any]:
    """Resolve work_item_statuses from the request, ensuring list is canonical."""
    statuses = list(col_req.resolved_statuses())
    col_dict["work_item_statuses"] = statuses
    # Keep work_item_status as first status for backward compat
    col_dict["work_item_status"] = statuses[0] if statuses else ""
    return col_dict


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
    data["columns"] = [
        _normalize_column(c, col_req)
        for c, col_req in zip(data["columns"], body.columns, strict=True)
    ]
    await store.add(data)
    await dispatch_event(
        request,
        BoardCreated(payload={"resource_id": body.board_id, "name": body.name}),
        stream_id=f"board:{body.board_id}",
    )
    result = await store.get(body.board_id)
    return result  # type: ignore[return-value]


@router.get("/boards")
async def list_all_boards(
    store: BoardStore = Depends(board_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all()


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
    if "columns" in updates and body.columns is not None:
        updates["columns"] = [
            _normalize_column(c, col_req)
            for c, col_req in zip(updates["columns"], body.columns, strict=True)
        ]
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


# ---------------------------------------------------------------------------
# Kanban view
# ---------------------------------------------------------------------------


class KanbanColumn(BaseModel):
    """A single column in the kanban view with its work items."""

    column_id: str
    name: str
    position: int
    wip_limit: int = 0
    work_items: list[dict[str, Any]] = Field(default_factory=list)


class KanbanView(BaseModel):
    """Board kanban view grouping work items by column."""

    board_id: str
    board_name: str
    columns: list[KanbanColumn] = Field(default_factory=list)


@router.get("/boards/{board_id}/kanban")
async def get_kanban_view(
    board_id: str,
    tags: str | None = Query(default=None, description="Comma-separated tag filter"),
    board_store: BoardStore = Depends(board_store_provider),  # noqa: B008
    wi_store: WorkItemStore = Depends(work_item_store_provider),  # noqa: B008
) -> KanbanView:
    board = await board_store.get(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")

    project_id: str = board["project_id"]
    all_items = await wi_store.list_all(project_id=project_id)

    # Filter by tags if requested
    if tags:
        tag_set = {t.strip() for t in tags.split(",") if t.strip()}
        all_items = [item for item in all_items if tag_set.intersection(item.get("tags", ()) or ())]

    # Build column lookup
    columns_data: list[dict[str, Any]] = board.get("columns", [])
    columns_by_id: dict[str, KanbanColumn] = {}
    ordered_columns: list[KanbanColumn] = []

    for col in sorted(columns_data, key=lambda c: c.get("position", 0)):
        kc = KanbanColumn(
            column_id=col["column_id"],
            name=col["name"],
            position=col.get("position", 0),
            wip_limit=col.get("wip_limit", 0),
        )
        columns_by_id[col["column_id"]] = kc
        ordered_columns.append(kc)

    # Place work items into columns by column_id, sorted by column_position
    for item in sorted(all_items, key=lambda i: i.get("column_position", 0)):
        col_id = item.get("column_id", "")
        if col_id in columns_by_id:
            columns_by_id[col_id].work_items.append(item)

    return KanbanView(
        board_id=board_id,
        board_name=board.get("name", ""),
        columns=ordered_columns,
    )
