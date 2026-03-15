"""Tests for automation domain types."""

from dataclasses import FrozenInstanceError, asdict

import pytest

from lintel.contracts.events import EVENT_TYPE_MAP
from lintel.domain.events import (
    AutomationCancelled,
    AutomationCreated,
    AutomationDisabled,
    AutomationEnabled,
    AutomationFired,
    AutomationRemoved,
    AutomationSkipped,
    AutomationUpdated,
)
from lintel.domain.types import (
    AutomationDefinition,
    AutomationTriggerType,
    ConcurrencyPolicy,
)


class TestAutomationTriggerType:
    def test_cron_value(self) -> None:
        assert AutomationTriggerType.CRON == "cron"

    def test_event_value(self) -> None:
        assert AutomationTriggerType.EVENT == "event"

    def test_manual_value(self) -> None:
        assert AutomationTriggerType.MANUAL == "manual"


class TestConcurrencyPolicy:
    def test_allow_value(self) -> None:
        assert ConcurrencyPolicy.ALLOW == "allow"

    def test_queue_value(self) -> None:
        assert ConcurrencyPolicy.QUEUE == "queue"

    def test_skip_value(self) -> None:
        assert ConcurrencyPolicy.SKIP == "skip"

    def test_cancel_value(self) -> None:
        assert ConcurrencyPolicy.CANCEL == "cancel"


class TestAutomationDefinition:
    def test_create_minimal(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Nightly Review",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.CRON,
            trigger_config={"schedule": "0 2 * * *", "timezone": "UTC"},
        )
        assert auto.automation_id == "a-1"
        assert auto.concurrency_policy == ConcurrencyPolicy.QUEUE
        assert auto.enabled is True
        assert auto.max_chain_depth == 3

    def test_frozen(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Test",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.MANUAL,
            trigger_config={},
        )
        with pytest.raises(FrozenInstanceError):
            auto.name = "Changed"  # type: ignore[misc]

    def test_asdict_roundtrip(self) -> None:
        auto = AutomationDefinition(
            automation_id="a-1",
            name="Test",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.EVENT,
            trigger_config={"event_types": ["PipelineRunCompleted"]},
            input_parameters={"branch": "main"},
            concurrency_policy=ConcurrencyPolicy.SKIP,
        )
        d = asdict(auto)
        assert d["automation_id"] == "a-1"
        assert d["trigger_config"]["event_types"] == ["PipelineRunCompleted"]
        assert d["concurrency_policy"] == "skip"


class TestAutomationEvents:
    def test_event_type_values(self) -> None:
        assert AutomationCreated.event_type == "AutomationCreated"
        assert AutomationUpdated.event_type == "AutomationUpdated"
        assert AutomationRemoved.event_type == "AutomationRemoved"
        assert AutomationEnabled.event_type == "AutomationEnabled"
        assert AutomationDisabled.event_type == "AutomationDisabled"
        assert AutomationFired.event_type == "AutomationFired"
        assert AutomationSkipped.event_type == "AutomationSkipped"
        assert AutomationCancelled.event_type == "AutomationCancelled"

    def test_events_in_registry(self) -> None:
        for name in [
            "AutomationCreated",
            "AutomationUpdated",
            "AutomationRemoved",
            "AutomationEnabled",
            "AutomationDisabled",
            "AutomationFired",
            "AutomationSkipped",
            "AutomationCancelled",
        ]:
            assert name in EVENT_TYPE_MAP, f"{name} missing from EVENT_TYPE_MAP"
