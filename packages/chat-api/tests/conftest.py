"""Test configuration for lintel-chat-api."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


def _seed_workflow_definitions(app: object) -> None:
    """Seed the workflow definition store so classify sees enabled workflows."""
    from lintel.workflow_definitions_api.routes import workflow_definition_store_provider

    store = workflow_definition_store_provider.get()

    async def _seed() -> None:
        await store.put(
            "feature_to_pr",
            {
                "definition_id": "feature_to_pr",
                "name": "Feature to PR",
                "enabled": True,
            },
        )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()


@pytest.fixture()
def client() -> Generator[TestClient]:
    """TestClient with in-memory backend, keyword-only chat router (no LLM)."""
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    with TestClient(create_app()) as c:
        _seed_workflow_definitions(c.app)
        # Replace the chat router with one that has no model_router so it uses
        # keyword classification only and doesn't try to call Ollama/LLM.
        from lintel.chat_api.chat_router import ChatRouter

        c.app.state.chat_router = ChatRouter(model_router=None)
        # Mock the command dispatcher so async workflow dispatch is a no-op
        # (prevents pre-flight checks from changing work item status in tests).
        c.app.state.command_dispatcher = AsyncMock()
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)
