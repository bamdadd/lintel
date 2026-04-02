"""Tests for the TemplateEngine."""

from __future__ import annotations

import pytest

from lintel.domain.templates.engine import TemplateEngine
from lintel.domain.templates.types import (
    StageConfig,
    TemplateCategory,
    TemplateParameter,
    WorkflowTemplate,
)


@pytest.fixture()
def engine() -> TemplateEngine:
    return TemplateEngine()


@pytest.fixture()
def template() -> WorkflowTemplate:
    return WorkflowTemplate(
        id="test_tmpl",
        name="Test Template",
        description="A test template",
        category=TemplateCategory.FEATURE,
        stages=(
            StageConfig(name="ingest", stage_type="ingest"),
            StageConfig(name="build", stage_type="implement"),
            StageConfig(name="gate", stage_type="approval", requires_approval=True),
        ),
        default_config={"timeout": 300},
        parameters=(
            TemplateParameter(name="repo_url", type="str", required=True),
            TemplateParameter(name="branch", type="str", default_value="main"),
            TemplateParameter(name="retries", type="int", default_value=3),
        ),
    )


def test_validate_params_valid(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    errors = engine.validate_params(template, {"repo_url": "https://gh.com/x"})
    assert errors == []


def test_validate_params_missing_required(
    engine: TemplateEngine, template: WorkflowTemplate
) -> None:
    errors = engine.validate_params(template, {})
    assert any("repo_url" in e for e in errors)


def test_validate_params_unknown_param(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    errors = engine.validate_params(template, {"repo_url": "x", "bogus": "y"})
    assert any("bogus" in e for e in errors)


def test_validate_params_wrong_type(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    errors = engine.validate_params(template, {"repo_url": "x", "retries": "not_int"})
    assert any("retries" in e for e in errors)


def test_validate_params_multiple_errors(
    engine: TemplateEngine, template: WorkflowTemplate
) -> None:
    errors = engine.validate_params(template, {"unknown": 1, "retries": "bad"})
    assert len(errors) >= 2


def test_instantiate_success(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    result = engine.instantiate(template, {"repo_url": "https://gh.com/x"})
    assert result["definition_id"] == "test_tmpl"
    assert result["name"] == "Test Template"
    assert result["stage_names"] == ("ingest", "build", "gate")
    assert result["approval_stages"] == ("gate",)
    assert result["config"]["repo_url"] == "https://gh.com/x"
    assert result["config"]["branch"] == "main"  # default applied
    assert result["config"]["timeout"] == 300  # from default_config


def test_instantiate_override_default(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    result = engine.instantiate(template, {"repo_url": "x", "branch": "dev"})
    assert result["config"]["branch"] == "dev"


def test_instantiate_no_params_uses_defaults(engine: TemplateEngine) -> None:
    t = WorkflowTemplate(
        id="simple",
        name="Simple",
        stages=(StageConfig(name="a", stage_type="ingest"),),
        parameters=(TemplateParameter(name="x", type="str", default_value="hello"),),
    )
    result = engine.instantiate(t)
    assert result["config"]["x"] == "hello"


def test_instantiate_raises_on_invalid(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    with pytest.raises(ValueError, match="Invalid parameters"):
        engine.instantiate(template, {})


def test_instantiate_stage_types(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    result = engine.instantiate(template, {"repo_url": "x"})
    assert result["stage_types"]["ingest"] == "ingest"
    assert result["stage_types"]["gate"] == "approval"


def test_instantiate_category(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    result = engine.instantiate(template, {"repo_url": "x"})
    assert result["category"] == "feature"


def test_instantiate_version(engine: TemplateEngine, template: WorkflowTemplate) -> None:
    result = engine.instantiate(template, {"repo_url": "x"})
    assert result["version"] == "1.0.0"
