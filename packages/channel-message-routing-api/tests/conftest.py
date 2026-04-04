"""Test fixtures for channel-message-routing-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.channel_message_routing_api.routes import router, routing_rule_store_provider
from lintel.channel_message_routing_api.store import InMemoryRoutingRuleStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryRoutingRuleStore()
    routing_rule_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    routing_rule_store_provider.override(None)
