"""Test fixtures for workflow-definitions-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    from lintel.api.app import create_app

    with TestClient(create_app()) as c:
        yield c
