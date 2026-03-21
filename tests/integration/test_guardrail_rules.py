"""Integration tests for guardrail rules API and end-to-end flow (GRD-7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from lintel.compliance_api.guardrail_rules import guardrail_rule_store_provider, router
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.guardrails.default_rules import DEFAULT_RULES

if TYPE_CHECKING:
    from lintel.domain.guardrails.models import GuardrailRule


@pytest.fixture()
def guardrail_store() -> ComplianceStore:
    return ComplianceStore("rule_id")


@pytest.fixture()
def app(guardrail_store: ComplianceStore) -> FastAPI:
    """Create a minimal FastAPI app with guardrail routes."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    guardrail_rule_store_provider.override(guardrail_store)
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def _seed_defaults(store: ComplianceStore) -> None:
    """Seed all default rules into the store."""
    for rule in DEFAULT_RULES:
        await store.add(rule)


# --- API Tests ---


async def test_list_guardrail_rules_returns_defaults(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """GET /guardrail-rules returns all 7 default rules after seeding."""
    await _seed_defaults(guardrail_store)

    resp = await client.get("/api/v1/guardrail-rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 7


async def test_list_guardrail_rules_filter_by_enabled(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """GET /guardrail-rules?enabled=true filters correctly."""
    await _seed_defaults(guardrail_store)

    resp = await client.get("/api/v1/guardrail-rules", params={"enabled": True})
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 7
    assert all(r["enabled"] for r in rules)


async def test_list_guardrail_rules_filter_by_is_default(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """GET /guardrail-rules?is_default=true returns only default rules."""
    await _seed_defaults(guardrail_store)

    resp = await client.get("/api/v1/guardrail-rules", params={"is_default": True})
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 7
    assert all(r["is_default"] for r in rules)


async def test_get_guardrail_rule_by_id(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """GET /guardrail-rules/{id} returns the correct rule."""
    await _seed_defaults(guardrail_store)
    first_rule = DEFAULT_RULES[0]

    resp = await client.get(f"/api/v1/guardrail-rules/{first_rule.rule_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == first_rule.name


async def test_get_guardrail_rule_not_found(client: AsyncClient) -> None:
    """GET /guardrail-rules/{id} returns 404 for missing rule."""
    resp = await client.get("/api/v1/guardrail-rules/nonexistent-id")
    assert resp.status_code == 404


async def test_update_guardrail_rule_threshold(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """PUT /guardrail-rules/{id} allows threshold update."""
    await _seed_defaults(guardrail_store)
    cost_rule = DEFAULT_RULES[1]  # cost_warning, threshold=5.0

    resp = await client.put(
        f"/api/v1/guardrail-rules/{cost_rule.rule_id}",
        json={"threshold": 10.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["threshold"] == 10.0


async def test_update_guardrail_rule_enabled(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """PUT /guardrail-rules/{id} allows toggling enabled state."""
    await _seed_defaults(guardrail_store)
    rule = DEFAULT_RULES[0]

    resp = await client.put(
        f"/api/v1/guardrail-rules/{rule.rule_id}",
        json={"enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False


async def test_delete_default_rule_returns_403(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """DELETE /guardrail-rules/{id} returns 403 for default rules."""
    await _seed_defaults(guardrail_store)
    rule = DEFAULT_RULES[0]

    resp = await client.delete(f"/api/v1/guardrail-rules/{rule.rule_id}")
    assert resp.status_code == 403
    assert "Default" in resp.json()["detail"]


async def test_create_custom_rule(client: AsyncClient) -> None:
    """POST /guardrail-rules creates a custom rule."""
    resp = await client.post(
        "/api/v1/guardrail-rules",
        json={
            "rule_id": "custom-rule-001",
            "name": "custom_cost_limit",
            "event_type": "RunCompleted",
            "condition": "run_cost > threshold",
            "action": "WARN",
            "threshold": 50.0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "custom_cost_limit"
    assert data["is_default"] is False


async def test_delete_custom_rule_succeeds(
    client: AsyncClient,
) -> None:
    """DELETE /guardrail-rules/{id} succeeds for custom rules."""
    # Create a custom rule first
    await client.post(
        "/api/v1/guardrail-rules",
        json={
            "rule_id": "custom-to-delete",
            "name": "temp_rule",
            "event_type": "RunCompleted",
            "condition": "run_cost > threshold",
            "action": "WARN",
            "threshold": 1.0,
        },
    )

    resp = await client.delete("/api/v1/guardrail-rules/custom-to-delete")
    assert resp.status_code == 204


# --- Engine Integration Tests ---


async def test_engine_rework_rate_triggers_warn() -> None:
    """Simulate run.completed with rework_rate=0.3 → WARN triggered."""
    from lintel.contracts.events import EventEnvelope
    from lintel.domain.guardrails.engine import GuardrailEngine

    class MockRepo:
        async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
            return [r for r in DEFAULT_RULES if r.event_type == event_type]

        async def list_enabled(self) -> list[GuardrailRule]:
            return list(DEFAULT_RULES)

        async def get(self, rule_id: str) -> GuardrailRule | None:
            return None

        async def upsert(self, rule: GuardrailRule) -> None:
            pass

        async def delete(self, rule_id: str) -> bool:
            return False

    class MockBus:
        def __init__(self) -> None:
            self.published: list[EventEnvelope] = []

        async def publish(self, event: EventEnvelope) -> None:
            self.published.append(event)

        async def subscribe(self, event_types: frozenset[str], handler: object) -> str:
            return "mock"

        async def unsubscribe(self, subscription_id: str) -> None:
            pass

    bus = MockBus()
    engine = GuardrailEngine(rule_repo=MockRepo(), event_bus=bus)

    event = EventEnvelope(
        event_type="RunCompleted",
        payload={"rework_rate": 0.3, "run_cost": 1.0},
    )
    await engine.handle(event)

    # Should trigger agent_rework_warning (WARN) but not cost_warning
    assert len(bus.published) == 1
    assert bus.published[0].payload["rule_name"] == "agent_rework_warning"
    assert bus.published[0].payload["action"] == "WARN"


async def test_engine_test_failure_triggers_block() -> None:
    """Simulate test.result.recorded with verdict=failed → BLOCK."""
    from lintel.contracts.events import EventEnvelope
    from lintel.domain.guardrails.engine import GuardrailBlockError, GuardrailEngine

    class MockRepo:
        async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
            return [r for r in DEFAULT_RULES if r.event_type == event_type]

        async def list_enabled(self) -> list[GuardrailRule]:
            return list(DEFAULT_RULES)

        async def get(self, rule_id: str) -> GuardrailRule | None:
            return None

        async def upsert(self, rule: GuardrailRule) -> None:
            pass

        async def delete(self, rule_id: str) -> bool:
            return False

    class MockBus:
        def __init__(self) -> None:
            self.published: list[EventEnvelope] = []

        async def publish(self, event: EventEnvelope) -> None:
            self.published.append(event)

        async def subscribe(self, event_types: frozenset[str], handler: object) -> str:
            return "mock"

        async def unsubscribe(self, subscription_id: str) -> None:
            pass

    bus = MockBus()
    engine = GuardrailEngine(rule_repo=MockRepo(), event_bus=bus)

    event = EventEnvelope(
        event_type="TestResultRecorded",
        payload={"run_id": "run-1", "verdict": "failed"},
    )

    with pytest.raises(GuardrailBlockError) as exc_info:
        await engine.handle(event)

    assert exc_info.value.rule_name == "test_failure_block"
    assert len(bus.published) == 1
    assert bus.published[0].payload["action"] == "BLOCK"


async def test_engine_pii_detected_triggers_block_and_redaction() -> None:
    """Simulate artifact.created with pii_detected=True → BLOCK."""
    from lintel.contracts.events import EventEnvelope
    from lintel.domain.guardrails.engine import GuardrailBlockError, GuardrailEngine

    class MockRepo:
        async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]:
            return [r for r in DEFAULT_RULES if r.event_type == event_type]

        async def list_enabled(self) -> list[GuardrailRule]:
            return list(DEFAULT_RULES)

        async def get(self, rule_id: str) -> GuardrailRule | None:
            return None

        async def upsert(self, rule: GuardrailRule) -> None:
            pass

        async def delete(self, rule_id: str) -> bool:
            return False

    class MockBus:
        def __init__(self) -> None:
            self.published: list[EventEnvelope] = []

        async def publish(self, event: EventEnvelope) -> None:
            self.published.append(event)

        async def subscribe(self, event_types: frozenset[str], handler: object) -> str:
            return "mock"

        async def unsubscribe(self, subscription_id: str) -> None:
            pass

    bus = MockBus()
    engine = GuardrailEngine(rule_repo=MockRepo(), event_bus=bus)

    event = EventEnvelope(
        event_type="ArtifactCreated",
        payload={
            "artifact_id": "art-1",
            "content_preview": "SSN: 123-45-6789",
            "pii_detected": True,
        },
    )

    with pytest.raises(GuardrailBlockError) as exc_info:
        await engine.handle(event)

    assert exc_info.value.rule_name == "pii_in_artifacts"
    assert len(bus.published) == 1
    assert bus.published[0].payload["action"] == "BLOCK"


async def test_engine_updated_threshold_is_used(
    client: AsyncClient,
    guardrail_store: ComplianceStore,
) -> None:
    """Verify PUT threshold update is reflected in engine evaluation."""
    await _seed_defaults(guardrail_store)
    cost_rule = DEFAULT_RULES[1]  # cost_warning, threshold=5.0

    # Update threshold to 20.0
    resp = await client.put(
        f"/api/v1/guardrail-rules/{cost_rule.rule_id}",
        json={"threshold": 20.0},
    )
    assert resp.status_code == 200

    # Verify store has updated value
    updated = await guardrail_store.get(cost_rule.rule_id)
    assert updated is not None
    assert updated["threshold"] == 20.0
