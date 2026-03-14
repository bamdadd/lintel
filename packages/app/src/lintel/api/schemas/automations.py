"""Pydantic schemas for automation endpoints."""

from uuid import uuid4

from croniter import croniter  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, model_validator

from lintel.contracts.types import AutomationTriggerType, ConcurrencyPolicy


def _validate_trigger_config(
    trigger_type: AutomationTriggerType,
    trigger_config: dict[str, object],
    instance: object,
) -> object:
    """Validate trigger_config shape matches trigger_type."""
    if trigger_type == AutomationTriggerType.CRON:
        schedule = trigger_config.get("schedule")
        if not schedule or not isinstance(schedule, str):
            msg = "Cron trigger requires 'schedule' string in trigger_config"
            raise ValueError(msg)
        if not croniter.is_valid(str(schedule)):
            msg = f"Invalid cron expression: {schedule}"
            raise ValueError(msg)
    elif trigger_type == AutomationTriggerType.EVENT:
        event_types = trigger_config.get("event_types")
        if not event_types or not isinstance(event_types, list) or len(event_types) == 0:
            msg = "Event trigger requires non-empty 'event_types' list in trigger_config"
            raise ValueError(msg)
    return instance


class CreateAutomationRequest(BaseModel):
    automation_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    project_id: str
    workflow_definition_id: str
    trigger_type: AutomationTriggerType
    trigger_config: dict[str, object]
    input_parameters: dict[str, object] = Field(default_factory=dict)
    concurrency_policy: ConcurrencyPolicy = ConcurrencyPolicy.QUEUE
    enabled: bool = True

    @model_validator(mode="after")
    def validate_trigger_config(self) -> "CreateAutomationRequest":
        _validate_trigger_config(self.trigger_type, self.trigger_config, self)
        return self


class UpdateAutomationRequest(BaseModel):
    name: str | None = None
    trigger_config: dict[str, object] | None = None
    input_parameters: dict[str, object] | None = None
    concurrency_policy: ConcurrencyPolicy | None = None
    enabled: bool | None = None
    max_chain_depth: int | None = None
