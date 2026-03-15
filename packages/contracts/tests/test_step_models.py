"""Tests for NodeType enum and ProjectStepModelOverride contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest


class TestNodeType:
    def test_node_type_is_str_enum(self) -> None:
        from lintel.contracts.step_models import NodeType

        assert isinstance(NodeType.RESEARCH, str)

    def test_node_type_values(self) -> None:
        from lintel.contracts.step_models import NodeType

        assert NodeType.RESEARCH == "research"
        assert NodeType.PLAN == "plan"
        assert NodeType.IMPLEMENT == "implement"
        assert NodeType.REVIEW == "review"
        assert NodeType.TEST == "test"
        assert NodeType.TRIAGE == "triage"
        assert NodeType.ANALYSE == "analyse"

    def test_node_type_has_expected_members(self) -> None:
        from lintel.contracts.step_models import NodeType

        values = {n.value for n in NodeType}
        assert "research" in values
        assert "plan" in values
        assert "implement" in values
        assert "review" in values


class TestProjectStepModelOverride:
    def test_create_override(self) -> None:
        from lintel.contracts.step_models import NodeType, ProjectStepModelOverride

        project_id = uuid4()
        now = datetime.now(tz=UTC)
        override = ProjectStepModelOverride(
            project_id=project_id,
            node_type=NodeType.RESEARCH,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            created_at=now,
            updated_at=now,
        )
        assert override.project_id == project_id
        assert override.node_type == NodeType.RESEARCH
        assert override.provider == "anthropic"
        assert override.model == "claude-3-5-sonnet-20241022"

    def test_override_is_frozen(self) -> None:
        from pydantic import ValidationError

        from lintel.contracts.step_models import NodeType, ProjectStepModelOverride

        now = datetime.now(tz=UTC)
        override = ProjectStepModelOverride(
            project_id=uuid4(),
            node_type=NodeType.PLAN,
            provider="openai",
            model="gpt-4o",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises((ValidationError, TypeError)):
            override.provider = "ollama"  # type: ignore[misc]

    def test_override_project_id_is_uuid(self) -> None:
        from lintel.contracts.step_models import NodeType, ProjectStepModelOverride

        now = datetime.now(tz=UTC)
        override = ProjectStepModelOverride(
            project_id=uuid4(),
            node_type=NodeType.IMPLEMENT,
            provider="ollama",
            model="llama3.1:8b",
            created_at=now,
            updated_at=now,
        )
        assert isinstance(override.project_id, UUID)


class TestStepModelOverrideRequest:
    def test_request_has_provider_and_model(self) -> None:
        from lintel.contracts.step_models import StepModelOverrideRequest

        req = StepModelOverrideRequest(provider="anthropic", model="claude-3-5-sonnet-20241022")
        assert req.provider == "anthropic"
        assert req.model == "claude-3-5-sonnet-20241022"

    def test_request_is_pydantic_model(self) -> None:
        from pydantic import BaseModel

        from lintel.contracts.step_models import StepModelOverrideRequest

        assert issubclass(StepModelOverrideRequest, BaseModel)

    def test_request_validates_required_fields(self) -> None:
        from pydantic import ValidationError

        from lintel.contracts.step_models import StepModelOverrideRequest

        with pytest.raises(ValidationError):
            StepModelOverrideRequest(provider="anthropic")  # type: ignore[call-arg]


class TestStepModelOverrideResponse:
    def test_response_has_all_fields(self) -> None:
        from lintel.contracts.step_models import NodeType, StepModelOverrideResponse

        project_id = uuid4()
        now = datetime.now(tz=UTC)
        resp = StepModelOverrideResponse(
            project_id=project_id,
            node_type=NodeType.REVIEW,
            provider="openai",
            model="gpt-4o",
            created_at=now,
            updated_at=now,
        )
        assert resp.project_id == project_id
        assert resp.node_type == NodeType.REVIEW
        assert resp.provider == "openai"
        assert resp.model == "gpt-4o"
        assert resp.created_at == now
        assert resp.updated_at == now

    def test_response_is_pydantic_model(self) -> None:
        from pydantic import BaseModel

        from lintel.contracts.step_models import StepModelOverrideResponse

        assert issubclass(StepModelOverrideResponse, BaseModel)


class TestContractsExports:
    def test_exports_from_init(self) -> None:
        from lintel.contracts import (
            NodeType,
            ProjectStepModelOverride,
            StepModelOverrideRequest,
            StepModelOverrideResponse,
        )

        assert NodeType is not None
        assert ProjectStepModelOverride is not None
        assert StepModelOverrideRequest is not None
        assert StepModelOverrideResponse is not None
