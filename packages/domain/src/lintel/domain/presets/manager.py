"""PresetManager — register, compose, and validate workflow presets."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.presets.types import (
        ComposedConfig,
        PresetCategory,
        WorkflowPreset,
    )


class PresetManager:
    """Registry and composition engine for workflow presets."""

    def __init__(self) -> None:
        self._presets: dict[str, WorkflowPreset] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, preset: WorkflowPreset) -> None:
        """Register a preset (overwrites if same preset_id exists)."""
        self._presets[preset.preset_id] = preset

    def get(self, preset_id: str) -> WorkflowPreset | None:
        """Return a preset by id, or ``None``."""
        return self._presets.get(preset_id)

    def list(self, category_filter: PresetCategory | None = None) -> list[WorkflowPreset]:
        """List presets, optionally filtered by category."""
        presets = list(self._presets.values())
        if category_filter is not None:
            presets = [p for p in presets if p.category == category_filter]
        return sorted(presets, key=lambda p: (p.category.value, p.name))

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self, preset_ids: list[str]) -> ComposedConfig:
        """Merge overrides from the given presets, ordered by priority.

        Lower-priority presets are applied first so higher-priority ones win.
        Returns a flat ``{key: value}`` mapping.
        """
        resolved: list[WorkflowPreset] = []
        for pid in preset_ids:
            preset = self._presets.get(pid)
            if preset is not None:
                resolved.append(preset)

        # Sort ascending by priority — last write wins.
        resolved.sort()

        result: ComposedConfig = {}
        for preset in resolved:
            result.update(preset.as_dict())
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_compatibility(
        self,
        preset_ids: list[str],
        workflow_type: str,
    ) -> list[str]:
        """Check that all presets are compatible with *workflow_type*.

        Returns a list of human-readable conflict descriptions.
        An empty list means no conflicts.
        """
        conflicts: list[str] = []
        for pid in preset_ids:
            preset = self._presets.get(pid)
            if preset is None:
                conflicts.append(f"Preset '{pid}' not found")
                continue
            if preset.compatible_workflows and workflow_type not in preset.compatible_workflows:
                conflicts.append(
                    f"Preset '{preset.name}' ({pid}) is not compatible "
                    f"with workflow type '{workflow_type}'"
                )
        return conflicts
