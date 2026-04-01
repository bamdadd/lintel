"""Test fixtures for auth-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.auth_api.middleware import JWTAuthMiddleware
from lintel.auth_api.routes import auth_user_store_provider, router
from lintel.auth_api.store import InMemoryAuthUserStore
from lintel.domain.auth.passwords import hash_password
from lintel.domain.auth.types import AuthRole, AuthUser

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def store() -> InMemoryAuthUserStore:
    return InMemoryAuthUserStore()


@pytest.fixture()
def client(store: InMemoryAuthUserStore) -> Generator[TestClient]:
    auth_user_store_provider.override(store)
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    auth_user_store_provider.override(None)


@pytest.fixture()
async def seeded_store(store: InMemoryAuthUserStore) -> InMemoryAuthUserStore:
    user = AuthUser(
        user_id=str(uuid4()),
        email="alice@example.com",
        name="Alice",
        hashed_password=hash_password("correct-password"),
        role=AuthRole.ADMIN,
    )
    await store.add(user)
    return store
