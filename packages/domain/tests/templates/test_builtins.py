"""Tests for built-in workflow templates."""

from __future__ import annotations

from lintel.domain.templates.builtins import (
    BUILTIN_TEMPLATES,
    CODE_REVIEW,
    FEATURE_TO_PR,
    INCIDENT_RESPONSE,
)
from lintel.domain.templates.engine import TemplateEngine
from lintel.domain.templates.types import TemplateCategory


def test_builtin_count() -> None:
    assert len(BUILTIN_TEMPLATES) == 3


def test_feature_to_pr_id() -> None:
    assert FEATURE_TO_PR.id == "feature_to_pr"
    assert FEATURE_TO_PR.category == TemplateCategory.FEATURE
    assert len(FEATURE_TO_PR.stages) == 11


def test_code_review_id() -> None:
    assert CODE_REVIEW.id == "code_review"
    assert CODE_REVIEW.category == TemplateCategory.REVIEW
    assert len(CODE_REVIEW.stages) == 4


def test_incident_response_id() -> None:
    assert INCIDENT_RESPONSE.id == "incident_response"
    assert INCIDENT_RESPONSE.category == TemplateCategory.BUGFIX
    assert len(INCIDENT_RESPONSE.stages) == 6


def test_all_builtins_have_required_params() -> None:
    for t in BUILTIN_TEMPLATES:
        required = [p for p in t.parameters if p.required]
        assert len(required) >= 1, f"{t.id} should have at least one required param"


def test_feature_to_pr_instantiate() -> None:
    engine = TemplateEngine()
    result = engine.instantiate(FEATURE_TO_PR, {"repo_url": "https://github.com/org/repo"})
    assert result["definition_id"] == "feature_to_pr"
    assert "ingest" in result["stage_names"]
    assert "approve_research" in result["approval_stages"]


def test_code_review_instantiate() -> None:
    engine = TemplateEngine()
    result = engine.instantiate(CODE_REVIEW, {"pr_url": "https://github.com/org/repo/pull/1"})
    assert result["definition_id"] == "code_review"


def test_incident_response_instantiate() -> None:
    engine = TemplateEngine()
    result = engine.instantiate(INCIDENT_RESPONSE, {"incident_url": "https://pagerduty.com/x"})
    assert result["definition_id"] == "incident_response"
    assert result["config"]["severity"] == "p2"


def test_unique_template_ids() -> None:
    ids = [t.id for t in BUILTIN_TEMPLATES]
    assert len(ids) == len(set(ids))
