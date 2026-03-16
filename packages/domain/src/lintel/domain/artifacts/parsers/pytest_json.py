"""Pytest JSON report parser."""

from __future__ import annotations

import json
from typing import Any

from lintel.domain.artifacts.models import (
    ParsedArtifact,
    TestCase,
    TestCaseStatus,
    TestSuite,
)

_STATUS_MAP: dict[str, TestCaseStatus] = {
    "passed": TestCaseStatus.PASSED,
    "failed": TestCaseStatus.FAILED,
    "error": TestCaseStatus.ERROR,
    "skipped": TestCaseStatus.SKIPPED,
    "xfailed": TestCaseStatus.SKIPPED,
    "xpassed": TestCaseStatus.PASSED,
}


class PytestJSONParser:
    """Parse pytest JSON report format (pytest-json-report plugin)."""

    def parse(self, raw_bytes: bytes) -> ParsedArtifact:
        """Parse pytest JSON bytes into a ParsedArtifact."""
        data: dict[str, Any] = json.loads(raw_bytes)

        # Group tests by their module/file
        suites_map: dict[str, list[TestCase]] = {}
        tests = data.get("tests", [])

        for test in tests:
            nodeid: str = test.get("nodeid", "")
            # Extract module from nodeid (e.g., "tests/test_foo.py::TestBar::test_baz")
            parts = nodeid.split("::")
            module = parts[0] if parts else "unknown"

            outcome = test.get("outcome", "passed")
            status = _STATUS_MAP.get(outcome, TestCaseStatus.PASSED)

            # Duration is in seconds in pytest JSON
            duration_s = test.get("duration", 0.0)
            duration_ms = int(duration_s * 1000)

            message = ""
            output = ""
            call_info = test.get("call", {})
            if isinstance(call_info, dict) and call_info.get("longrepr"):
                message = str(call_info["longrepr"])[:200]
                output = str(call_info["longrepr"])

            case = TestCase(
                name=nodeid,
                classname=module,
                status=status,
                duration_ms=duration_ms,
                message=message,
                output=output,
            )
            suites_map.setdefault(module, []).append(case)

        suites: list[TestSuite] = []
        for module_name, cases in suites_map.items():
            total = len(cases)
            failed = sum(1 for c in cases if c.status == TestCaseStatus.FAILED)
            errors_count = sum(1 for c in cases if c.status == TestCaseStatus.ERROR)
            skipped = sum(1 for c in cases if c.status == TestCaseStatus.SKIPPED)
            passed = total - failed - errors_count - skipped
            duration_ms = sum(c.duration_ms for c in cases)

            suites.append(
                TestSuite(
                    name=module_name,
                    tests=tuple(cases),
                    total=total,
                    passed=passed,
                    failed=failed,
                    errors=errors_count,
                    skipped=skipped,
                    duration_ms=duration_ms,
                )
            )

        total = sum(s.total for s in suites)
        passed = sum(s.passed for s in suites)
        failed = sum(s.failed for s in suites)
        errors = sum(s.errors for s in suites)
        skipped = sum(s.skipped for s in suites)
        duration_ms = sum(s.duration_ms for s in suites)

        return ParsedArtifact(
            suites=tuple(suites),
            total=total,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration_ms=duration_ms,
        )
