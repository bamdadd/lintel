"""Post-stage hook for test stages (REQ-010).

Parses artifacts and dispatches events after test stage completion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.artifacts_api.store import CoverageMetricStore, ParsedTestResultStore
    from lintel.contracts.protocols import EventBus

logger = structlog.get_logger()


class TestStageHook:
    """Hook that fires after a test stage completes.

    Retrieves raw artifact bytes, selects a parser, saves parsed
    results, and publishes TestResultsParsed / CoverageMeasured
    events.
    """

    def __init__(
        self,
        parsed_result_store: ParsedTestResultStore,
        coverage_store: CoverageMetricStore,
        event_bus: EventBus | None = None,
    ) -> None:
        self._parsed_result_store = parsed_result_store
        self._coverage_store = coverage_store
        self._event_bus = event_bus

    async def on_stage_complete(
        self,
        *,
        run_id: str,
        project_id: str,
        stage_id: str,
        artifacts: list[dict[str, Any]],
    ) -> None:
        """Process test artifacts after a stage completes."""
        from dataclasses import asdict
        from uuid import uuid4

        from lintel.domain.artifacts.parsers.registry import (
            ParserRegistry,
        )
        from lintel.domain.events import (
            CoverageMeasured,
            TestResultsParsed,
        )

        registry = ParserRegistry()

        for artifact in artifacts:
            raw_bytes: bytes = artifact.get("content", b"")
            if isinstance(raw_bytes, str):
                raw_bytes = raw_bytes.encode("utf-8")

            mime_type = artifact.get("mime_type")
            extension = artifact.get("extension")
            artifact_type = artifact.get(
                "artifact_type",
                "test_result",
            )
            artifact_id = artifact.get(
                "artifact_id",
                str(uuid4()),
            )

            try:
                if artifact_type == "coverage":
                    parser = registry.get_coverage_parser(
                        mime_type=mime_type,
                        extension=extension,
                    )
                    report = parser.parse(raw_bytes)

                    await self._coverage_store.save(
                        metric_id=str(uuid4()),
                        run_id=run_id,
                        project_id=project_id,
                        artifact_id=artifact_id,
                        data=asdict(report),
                    )
                    if self._event_bus:
                        await self._event_bus.publish(
                            CoverageMeasured(
                                payload={
                                    "run_id": run_id,
                                    "project_id": project_id,
                                    "artifact_id": artifact_id,
                                    "line_rate": (report.line_rate),
                                    "branch_rate": (report.branch_rate),
                                }
                            )
                        )
                else:
                    parser = registry.get_artifact_parser(
                        mime_type=mime_type,
                        extension=extension,
                    )
                    parsed = parser.parse(raw_bytes)

                    await self._parsed_result_store.save(
                        result_id=str(uuid4()),
                        run_id=run_id,
                        project_id=project_id,
                        artifact_id=artifact_id,
                        data=asdict(parsed),
                    )
                    if self._event_bus:
                        await self._event_bus.publish(
                            TestResultsParsed(
                                payload={
                                    "run_id": run_id,
                                    "project_id": project_id,
                                    "artifact_id": artifact_id,
                                    "total": parsed.total,
                                    "passed": parsed.passed,
                                    "failed": parsed.failed,
                                    "pass_rate": (parsed.pass_rate),
                                }
                            )
                        )
            except Exception:
                logger.warning(
                    "artifact_parse_failed",
                    run_id=run_id,
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    exc_info=True,
                )
