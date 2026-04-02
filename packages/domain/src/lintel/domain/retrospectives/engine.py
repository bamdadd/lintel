"""Retrospective engine — create, populate, and manage automated retrospectives (DL-4)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from lintel.domain.retrospectives.types import (
    ActionItem,
    ActionItemStatus,
    Observation,
    Retrospective,
    RetroStatus,
)


class RetroEngine:
    """In-memory retrospective engine for managing automated retrospectives."""

    def __init__(self) -> None:
        self._retros: dict[str, Retrospective] = {}

    def create_retro(
        self,
        project_id: str,
        period: tuple[datetime, datetime],
    ) -> Retrospective:
        """Create a new retrospective for *project_id* covering *period*."""
        retro = Retrospective(
            project_id=project_id,
            period_start=period[0],
            period_end=period[1],
            status=RetroStatus.PENDING,
        )
        self._retros[retro.retro_id] = retro
        return retro

    def add_observation(self, retro_id: str, observation: Observation) -> Retrospective:
        """Append an observation to a retrospective."""
        retro = self._get_or_raise(retro_id)
        updated = replace(retro, observations=(*retro.observations, observation))
        self._retros[retro_id] = updated
        return updated

    def generate_action_items(self, retro_id: str) -> list[ActionItem]:
        """Generate action items from the retrospective's observations.

        Creates one action item per observation and transitions the retro to in_progress.
        """
        retro = self._get_or_raise(retro_id)
        items: list[ActionItem] = []
        for obs in retro.observations:
            item = ActionItem(
                description=f"Address: {obs.description}",
                created_from_observation=obs.observation_id,
            )
            items.append(item)

        updated = replace(
            retro,
            action_items=(*retro.action_items, *items),
            status=RetroStatus.IN_PROGRESS,
        )
        self._retros[retro_id] = updated
        return items

    def complete(self, retro_id: str, summary: str) -> Retrospective:
        """Mark a retrospective as completed with a summary."""
        retro = self._get_or_raise(retro_id)
        updated = replace(retro, status=RetroStatus.COMPLETED, summary=summary)
        self._retros[retro_id] = updated
        return updated

    def get(self, retro_id: str) -> Retrospective | None:
        """Return a retrospective by id, or ``None``."""
        return self._retros.get(retro_id)

    def list_open_actions(self, project_id: str) -> list[ActionItem]:
        """Return all non-done action items across retrospectives for a project."""
        actions: list[ActionItem] = []
        for retro in self._retros.values():
            if retro.project_id == project_id:
                actions.extend(a for a in retro.action_items if a.status != ActionItemStatus.DONE)
        return actions

    def track_action(self, action_id: str, status: ActionItemStatus) -> ActionItem | None:
        """Update the status of an action item across all retrospectives.

        Returns the updated action item, or ``None`` if not found.
        """
        for retro_id, retro in self._retros.items():
            new_items: list[ActionItem] = []
            found = False
            result: ActionItem | None = None
            for item in retro.action_items:
                if item.action_id == action_id:
                    updated_item = replace(item, status=status)
                    new_items.append(updated_item)
                    found = True
                    result = updated_item
                else:
                    new_items.append(item)
            if found:
                self._retros[retro_id] = replace(retro, action_items=tuple(new_items))
                return result
        return None

    # -- helpers ---------------------------------------------------------------

    def _get_or_raise(self, retro_id: str) -> Retrospective:
        retro = self._retros.get(retro_id)
        if retro is None:
            msg = f"Retrospective {retro_id} not found"
            raise KeyError(msg)
        return retro
