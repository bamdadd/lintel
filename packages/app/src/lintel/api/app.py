"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from fastapi.routing import APIRoute

from lintel.api.lifespan import lifespan
from lintel.api.middleware import CorrelationMiddleware
from lintel.api.routers import mount_routers


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    def _generate_unique_id(route: APIRoute) -> str:
        if route.tags:
            return f"{route.tags[0]}_{route.name}"
        return route.name

    app = FastAPI(
        title="Lintel",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=_generate_unique_id,
    )
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
    )

    mount_routers(app)

    # Expose all API endpoints as MCP tools/resources
    from fastapi_mcp import FastApiMCP  # type: ignore[import-untyped]

    mcp = FastApiMCP(
        app,
        name="Lintel MCP",
        describe_all_responses=True,
    )
    mcp.mount_http()

    # Serve SPA static files in production (must be last)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=static_dir, html=True), name="spa")

    return app


app = create_app()
