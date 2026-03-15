"""Agent that orchestrates integration-pattern scanning for a repository."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
import uuid

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lightweight protocol stubs so the module is importable without hard
# dependencies on concrete event-store / event-bus implementations.
# ---------------------------------------------------------------------------


@runtime_checkable
class EventStore(Protocol):
    """Minimal event-store interface expected by the agent."""

    async def append(self, stream_id: str, event: dict[str, Any]) -> None: ...


@runtime_checkable
class EventBus(Protocol):
    """Minimal event-bus interface expected by the agent."""

    async def publish(self, topic: str, payload: dict[str, Any]) -> None: ...


class _NullEventStore:
    """No-op event store used when no real store is provided."""

    async def append(self, stream_id: str, event: dict[str, Any]) -> None:
        pass


class _NullEventBus:
    """No-op event bus used when no real bus is provided."""

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegrationScannerConfig:
    """Tuning knobs for the integration scanner agent."""

    file_extensions_filter: list[str] = field(default_factory=lambda: [".py"])
    coupling_threshold: float = 0.8
    enable_llm_analysis: bool = False


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class IntegrationScannerAgent:
    """Scans a repository for integration patterns and produces an integration map.

    The agent follows the AgentRuntime pattern:

    1. Accept domain-specific parameters (``repository_id``, ``config``).
    2. Expose an async ``run()`` method as the single entry-point.
    3. Publish lifecycle events via an ``EventBus``.
    4. Persist domain events via an ``EventStore``.
    """

    def __init__(
        self,
        repository_id: str,
        *,
        config: IntegrationScannerConfig | None = None,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository_id = repository_id
        self.config = config or IntegrationScannerConfig()
        self._event_store: EventStore = event_store or _NullEventStore()
        self._event_bus: EventBus = event_bus or _NullEventBus()
        self._log = logger.bind(
            agent="IntegrationScannerAgent",
            repository_id=repository_id,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> dict[str, Any]:
        """Execute the integration-scanning pipeline.

        Returns:
            A dict containing ``integration_map_id`` and ``summary`` keys.
        """
        integration_map_id = str(uuid.uuid4())
        stream_id = f"integration-scan-{integration_map_id}"

        # -- started -------------------------------------------------------
        started_event = {
            "type": "IntegrationScanStarted",
            "repository_id": self.repository_id,
            "integration_map_id": integration_map_id,
            "config": {
                "file_extensions_filter": self.config.file_extensions_filter,
                "coupling_threshold": self.config.coupling_threshold,
                "enable_llm_analysis": self.config.enable_llm_analysis,
            },
        }
        await self._event_store.append(stream_id, started_event)
        await self._event_bus.publish("integration_scan.started", started_event)
        self._log.info("integration_scan_started", map_id=integration_map_id)

        # -- invoke workflow graph -----------------------------------------
        scan_result = await self._extract_integration_patterns(integration_map_id)

        # -- completed -----------------------------------------------------
        summary = self._build_summary(scan_result)

        completed_event = {
            "type": "IntegrationScanCompleted",
            "repository_id": self.repository_id,
            "integration_map_id": integration_map_id,
            "summary": summary,
        }
        await self._event_store.append(stream_id, completed_event)
        await self._event_bus.publish("integration_scan.completed", completed_event)
        self._log.info(
            "integration_scan_completed",
            map_id=integration_map_id,
            **summary,
        )

        return {
            "integration_map_id": integration_map_id,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _extract_integration_patterns(
        self,
        integration_map_id: str,
    ) -> dict[str, Any]:
        """Invoke the ``extract_integration_patterns`` workflow graph.

        This is the seam where the concrete workflow engine is called.
        Subclasses or test doubles can override this method to inject
        alternative behaviour.
        """
        # Import lazily to avoid circular / hard dependencies at module level.
        from lintel.skills_api.integration_scanning import (
            build_dependency_graph,
            detect_antipatterns,
            scan_async_integrations,
            scan_db_integrations,
            scan_external_api_calls,
            scan_file_blob_integrations,
            scan_sync_integrations,
        )

        scan_results: dict[str, Any] = {}

        scanner_tasks = {
            "sync_integrations": scan_sync_integrations,
            "async_integrations": scan_async_integrations,
            "db_integrations": scan_db_integrations,
            "file_blob_integrations": scan_file_blob_integrations,
            "external_api_calls": scan_external_api_calls,
        }

        # TODO: resolve actual file paths from repository_id + file_extensions
        file_paths: list[str] = []

        for key, scanner_fn in scanner_tasks.items():
            try:
                scan_results[key] = await scanner_fn(file_paths)
            except Exception:
                self._log.exception("scanner_failed", scanner=key)
                scan_results[key] = []

        dependency_graph = await build_dependency_graph(scan_results)
        antipatterns = await detect_antipatterns(
            nodes=dependency_graph.get("nodes", []),
            edges=dependency_graph.get("edges", []),
            coupling_scores=dependency_graph.get("coupling_scores", []),
        )

        return {
            "scan_results": scan_results,
            "dependency_graph": dependency_graph,
            "antipatterns": antipatterns,
        }

    @staticmethod
    def _build_summary(scan_result: dict[str, Any]) -> dict[str, Any]:
        """Derive summary statistics from raw scan output."""
        scan_results = scan_result.get("scan_results", {})
        dep_graph = scan_result.get("dependency_graph", {})
        antipatterns = scan_result.get("antipatterns", [])

        total_patterns = sum(len(v) for v in scan_results.values() if isinstance(v, list))

        return {
            "total_patterns_detected": total_patterns,
            "node_count": len(dep_graph.get("nodes", [])),
            "edge_count": len(dep_graph.get("edges", [])),
            "antipattern_count": len(antipatterns) if isinstance(antipatterns, list) else 0,
        }
