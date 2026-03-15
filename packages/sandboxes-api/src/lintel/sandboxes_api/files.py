"""Sandbox file endpoints: read file, write file, get file tree."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.sandbox.errors import SandboxNotFoundError
from lintel.sandbox.events import SandboxFileWritten
from lintel.sandbox.types import SandboxJob

router = APIRouter()


class WriteFileRequest(BaseModel):
    path: str
    content: str


@router.post("/sandboxes/{sandbox_id}/files")
async def write_file(
    sandbox_id: str,
    body: WriteFileRequest,
    request: Request,
) -> dict[str, str]:
    """Write a file to the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        await manager.write_file(sandbox_id, body.path, body.content)
        await dispatch_event(
            request,
            SandboxFileWritten(payload={"resource_id": sandbox_id, "path": body.path}),
            stream_id=f"sandbox:{sandbox_id}",
        )
        return {"status": "written", "path": body.path}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/files")
async def read_file(
    sandbox_id: str,
    path: str,
    request: Request,
) -> dict[str, str]:
    """Read a file from the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        # Use cat via execute — more reliable than get_archive with cap_drop
        result = await manager.execute(
            sandbox_id,
            SandboxJob(command=f"cat {path}", timeout_seconds=10),
        )
        if result.exit_code != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot read file: {result.stderr.strip()}",
            )
        return {"path": path, "content": result.stdout}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/tree")
async def get_file_tree(
    sandbox_id: str,
    request: Request,
    path: str = "/workspace",
    depth: int = 3,
) -> dict[str, Any]:
    """Get a file tree from the sandbox, similar to Docker Desktop's file browser."""
    manager = request.app.state.sandbox_manager
    try:
        # Use find to build a structured tree — fast and reliable
        result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"find {path} -maxdepth {depth}"
                    f" -not -path '*/.git/*' -not -path '*/.git'"
                    f" -not -path '*/node_modules/*'"
                    f" -not -path '*/__pycache__/*'"
                    f" -not -path '*/.venv/*'"
                    " | head -2000"
                ),
                timeout_seconds=15,
            ),
        )
        if result.exit_code != 0:
            return {"path": path, "children": [], "error": result.stderr}

        lines = [ln for ln in result.stdout.strip().split("\n") if ln and ln != path]

        # Get file/dir info with stat
        stat_result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"find {path} -maxdepth {depth}"
                    f" -not -path '*/.git/*' -not -path '*/.git'"
                    f" -not -path '*/node_modules/*'"
                    f" -not -path '*/__pycache__/*'"
                    f" -not -path '*/.venv/*'"
                    " -printf '%y %s %p\\n'"
                    " | head -2000"
                ),
                timeout_seconds=15,
            ),
        )

        # Build lookup: path -> {type, size}
        info: dict[str, dict[str, Any]] = {}
        if stat_result.exit_code == 0:
            for ln in stat_result.stdout.strip().split("\n"):
                parts = ln.split(" ", 2)
                if len(parts) == 3:
                    info[parts[2]] = {
                        "type": "directory" if parts[0] == "d" else "file",
                        "size": int(parts[1]) if parts[0] != "d" else 0,
                    }

        # Build tree structure
        def build_tree(
            root: str,
            paths: list[str],
        ) -> list[dict[str, Any]]:
            children_map: dict[str, list[str]] = {}
            direct: list[str] = []
            root_depth = root.rstrip("/").count("/")

            for p in paths:
                p_depth = p.rstrip("/").count("/")
                if p_depth == root_depth + 1:
                    direct.append(p)
                elif p_depth > root_depth + 1:
                    # Find the direct parent at root_depth+1
                    parts = p.split("/")
                    parent = "/".join(parts[: root_depth + 2])
                    children_map.setdefault(parent, []).append(p)

            nodes: list[dict[str, Any]] = []
            for d in sorted(direct):
                meta = info.get(d, {"type": "file", "size": 0})
                name = d.rsplit("/", 1)[-1]
                node: dict[str, Any] = {
                    "name": name,
                    "path": d,
                    "type": meta["type"],
                }
                if meta["type"] == "file":
                    node["size"] = meta["size"]
                else:
                    sub_paths = children_map.get(d, [])
                    node["children"] = build_tree(d, sub_paths)
                nodes.append(node)

            # Sort: directories first, then files, alphabetical
            nodes.sort(key=lambda n: (0 if n["type"] == "directory" else 1, n["name"]))
            return nodes

        return {
            "path": path,
            "children": build_tree(path, lines),
        }
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.post("/sandboxes/{sandbox_id}/cleanup-workspace")
async def cleanup_workspace(
    sandbox_id: str,
    request: Request,
) -> dict[str, str]:
    """Remove all files from /workspace in the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "rm -rf /workspace/* /workspace/.[!.]* /workspace/..?* 2>/dev/null; echo ok"
                ),
                timeout_seconds=30,
            ),
        )
        if result.exit_code != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Cleanup failed: {result.stderr.strip()}",
            )
        return {"status": "cleaned", "sandbox_id": sandbox_id}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None
