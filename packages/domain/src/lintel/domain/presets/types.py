"""Workflow preset types — composable configuration profiles."""

from __future__ import annotations

from dataclasses import dataclass
import enum


class PresetCategory(enum.Enum):
    """Categories for workflow configuration presets."""

    SPEED = "speed"
    QUALITY = "quality"
    SECURITY = "security"
    COST = "cost"


@dataclass(frozen=True)
class PresetOverride:
    """A single configuration override within a preset."""

    key: str
    value: object
    description: str = ""


@dataclass(frozen=True)
class WorkflowPreset:
    """A composable workflow configuration preset."""

    preset_id: str
    name: str
    category: PresetCategory
    description: str = ""
    overrides: tuple[PresetOverride, ...] = ()
    compatible_workflows: tuple[str, ...] = ()
    priority: int = 0  # higher priority overrides win during composition

    @property
    def override_keys(self) -> frozenset[str]:
        """Return all override keys in this preset."""
        return frozenset(o.key for o in self.overrides)

    def as_dict(self) -> dict[str, object]:
        """Return overrides as a flat key-value mapping."""
        return {o.key: o.value for o in self.overrides}

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, WorkflowPreset):
            return NotImplemented
        return self.priority < other.priority

    def __le__(self, other: object) -> bool:
        if not isinstance(other, WorkflowPreset):
            return NotImplemented
        return self.priority <= other.priority

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, WorkflowPreset):
            return NotImplemented
        return self.priority > other.priority

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, WorkflowPreset):
            return NotImplemented
        return self.priority >= other.priority


# Re-usable type alias for override dicts produced by composition.
ComposedConfig = dict[str, object]
