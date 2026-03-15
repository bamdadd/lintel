"""Test configuration for lintel-chat-api."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

from lintel.api.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    """TestClient with in-memory backend, no mocked chat router."""
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)
