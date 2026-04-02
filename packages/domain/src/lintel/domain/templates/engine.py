"""Template engine — instantiates workflow definitions from templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.domain.templates.types import TemplateParameter, WorkflowTemplate


class TemplateEngine:
    """Instantiates workflow configurations from templates."""

    def validate_params(
        self,
        template: WorkflowTemplate,
        params: dict[str, Any],
    ) -> list[str]:
        """Validate parameters against a template's parameter definitions.

        Returns a list of validation error strings (empty if valid).
        """
        errors: list[str] = []
        param_defs: dict[str, TemplateParameter] = {p.name: p for p in template.parameters}

        # Check required parameters are present
        for p in template.parameters:
            if p.required and p.name not in params:
                errors.append(f"Missing required parameter: {p.name}")

        # Check for unknown parameters
        for key in params:
            if key not in param_defs:
                errors.append(f"Unknown parameter: {key}")

        # Type validation
        type_map: dict[str, type] = {
            "str": str,
            "int": int,
            "bool": bool,
            "float": float,
        }
        for key, value in params.items():
            if key in param_defs:
                expected_type = type_map.get(param_defs[key].type)
                if expected_type is not None and not isinstance(value, expected_type):
                    errors.append(
                        f"Parameter '{key}' must be {param_defs[key].type}, "
                        f"got {type(value).__name__}"
                    )

        return errors

    def instantiate(
        self,
        template: WorkflowTemplate,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Instantiate a workflow definition config from a template.

        Merges template defaults with user-supplied params. Raises ValueError
        if validation fails.

        Returns a dict suitable for creating a WorkflowDefinitionRecord.
        """
        params = params or {}
        errors = self.validate_params(template, params)
        if errors:
            raise ValueError(f"Invalid parameters: {'; '.join(errors)}")

        # Build resolved config: defaults + overrides
        resolved: dict[str, Any] = dict(template.default_config)
        # Apply parameter defaults then user values
        for p in template.parameters:
            if p.default_value is not None and p.name not in params:
                resolved[p.name] = p.default_value
        resolved.update(params)

        stage_names = tuple(s.name for s in template.stages)
        stage_types = {s.name: s.stage_type for s in template.stages}
        approval_stages = tuple(s.name for s in template.stages if s.requires_approval)

        return {
            "definition_id": template.id,
            "name": template.name,
            "description": template.description,
            "stage_names": stage_names,
            "stage_types": stage_types,
            "approval_stages": approval_stages,
            "config": resolved,
            "category": template.category.value,
            "tags": list(template.tags),
            "version": template.version,
        }
