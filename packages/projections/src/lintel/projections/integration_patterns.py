"""Projection that maintains a read-model of integration-pattern scan results."""

from __future__ import annotations

import copy
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class IntegrationPatternsProjection:
    """Read-model projection for integration scanning events.

    Implements the Projection protocol:
    - ``name`` -- identifier used by the projection engine.
    - ``handled_event_types`` -- the set of event types this projection cares about.
    - ``project(event)`` -- apply a single event to the in-memory state.
    - ``get_state()`` / ``restore_state(state)`` -- snapshot support.

    Accessor helpers ``get_map_summary`` and ``get_all_maps`` expose the
    materialised view for query consumers.
    """

    def __init__(self) -> None:
        self._state: dict[str, dict[str, Any]] = {}
        self._log = logger.bind(projection=self.name)

    # ------------------------------------------------------------------
    # Projection protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "integration_patterns"

    @property
    def handled_event_types(self) -> set[str]:
        return {
            "IntegrationScanStarted",
            "IntegrationScanCompleted",
            "IntegrationMapCreated",
            "IntegrationMapStatusUpdated",
        }

    def project(self, event: dict[str, Any]) -> None:
        """Apply *event* to the in-memory state.

        Unrecognised event types are silently ignored so that the
        projection is forward-compatible with future event versions.
        """
        event_type = event.get("type", "")

        if event_type == "IntegrationScanStarted":
            self._on_scan_started(event)
        elif event_type == "IntegrationScanCompleted":
            self._on_scan_completed(event)
        elif event_type == "IntegrationMapCreated":
            self._on_map_created(event)
        elif event_type == "IntegrationMapStatusUpdated":
            self._on_map_status_updated(event)
        else:
            self._log.debug("ignored_event_type", event_type=event_type)

    # ------------------------------------------------------------------
    # Snapshot support
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """Return a deep copy of the current state for snapshotting."""
        return copy.deepcopy(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore the projection from a previously snapshotted state."""
        self._state = copy.deepcopy(state)
        self._log.info("state_restored", map_count=len(self._state))

    # ------------------------------------------------------------------
    # Accessor helpers
    # ------------------------------------------------------------------

    def get_map_summary(self, map_id: str) -> dict[str, Any] | None:
        """Return the materialised summary for a single integration map.

        Returns ``None`` when *map_id* is not tracked by this projection.
        """
        record = self._state.get(map_id)
        if record is None:
            return None
        return copy.deepcopy(record)

    def get_all_maps(self) -> list[dict[str, Any]]:
        """Return summaries for every tracked integration map."""
        return [copy.deepcopy(record) for record in self._state.values()]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_scan_started(self, event: dict[str, Any]) -> None:
        map_id = event.get("integration_map_id", "")
        if not map_id:
            self._log.warning("scan_started_missing_map_id")
            return

        self._state[map_id] = {
            "integration_map_id": map_id,
            "repository_id": event.get("repository_id"),
            "status": "pending",
            "config": event.get("config"),
            "summary": None,
        }
        self._log.debug("scan_started_projected", map_id=map_id)

    def _on_scan_completed(self, event: dict[str, Any]) -> None:
        map_id = event.get("integration_map_id", "")
        record = self._state.get(map_id)
        if record is None:
            # Late arrival -- create a minimal record.
            record = {
                "integration_map_id": map_id,
                "repository_id": event.get("repository_id"),
                "config": None,
            }
            self._state[map_id] = record

        record["status"] = "completed"
        record["summary"] = event.get("summary")
        self._log.debug("scan_completed_projected", map_id=map_id)

    def _on_map_created(self, event: dict[str, Any]) -> None:
        map_id = event.get("integration_map_id", "")
        if not map_id:
            self._log.warning("map_created_missing_map_id")
            return

        record = self._state.get(map_id)
        if record is None:
            record = {
                "integration_map_id": map_id,
                "repository_id": event.get("repository_id"),
                "status": "created",
                "config": None,
                "summary": None,
            }
            self._state[map_id] = record

        # Index additional metadata supplied by the event.
        record["metadata"] = event.get("metadata")
        record.setdefault("status", "created")
        self._log.debug("map_created_projected", map_id=map_id)

    def _on_map_status_updated(self, event: dict[str, Any]) -> None:
        map_id = event.get("integration_map_id", "")
        record = self._state.get(map_id)
        if record is None:
            self._log.warning("status_update_for_unknown_map", map_id=map_id)
            return

        new_status = event.get("status")
        if new_status is not None:
            record["status"] = new_status
        self._log.debug(
            "map_status_updated_projected",
            map_id=map_id,
            status=new_status,
        )
