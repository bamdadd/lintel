"""Tests for workflow template domain types."""

from __future__ import annotations

from lintel.domain.templates.types import (
    StageConfig,
    TemplateCategory,
    TemplateParameter,
    WorkflowTemplate,
)


def test_template_category_values() -> None:
    assert TemplateCategory.FEATURE == "feature"
    assert TemplateCategory.BUGFIX == "bugfix"
    assert TemplateCategory.REVIEW == "review"
    assert TemplateCategory.DEPLOYMENT == "deployment"
    assert TemplateCategory.COMPLIANCE == "compliance"
    assert TemplateCategory.CUSTOM == "custom"


def test_template_parameter_defaults() -> None:
    p = TemplateParameter(name="x", type="str")
    assert p.default_value is None
    assert p.required is False
    assert p.description == ""


def test_template_parameter_with_values() -> None:
    p = TemplateParameter(
        name="branch", type="str", default_value="main", required=True, description="Branch"
    )
    assert p.name == "branch"
    assert p.default_value == "main"
    assert p.required is True


def test_stage_config_defaults() -> None:
    s = StageConfig(name="build", stage_type="implement")
    assert s.description == ""
    assert s.timeout_seconds == 0
    assert s.requires_approval is False


def test_stage_config_with_approval() -> None:
    s = StageConfig(name="gate", stage_type="approval", requires_approval=True)
    assert s.requires_approval is True


def test_workflow_template_defaults() -> None:
    t = WorkflowTemplate(id="test", name="Test")
    assert t.description == ""
    assert t.category == TemplateCategory.CUSTOM
    assert t.stages == ()
    assert t.default_config == {}
    assert t.parameters == ()
    assert t.tags == ()
    assert t.version == "1.0.0"


def test_workflow_template_frozen() -> None:
    t = WorkflowTemplate(id="test", name="Test")
    try:
        t.id = "changed"  # type: ignore[misc]
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_workflow_template_with_stages() -> None:
    stages = (
        StageConfig(name="a", stage_type="ingest"),
        StageConfig(name="b", stage_type="implement"),
    )
    t = WorkflowTemplate(id="t", name="T", stages=stages)
    assert len(t.stages) == 2
    assert t.stages[0].name == "a"
