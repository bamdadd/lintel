"""TAP (Test Anything Protocol) parser."""

from __future__ import annotations

import re

from lintel.domain.artifacts.models import (
    ParsedArtifact,
    TestCase,
    TestCaseStatus,
    TestSuite,
)

_TAP_LINE = re.compile(
    r"^(ok|not ok)\s+(\d+)?\s*(?:-\s*)?(.*?)(?:\s*#\s*(SKIP|TODO)\s*(.*))?$",
    re.IGNORECASE,
)
_PLAN_LINE = re.compile(r"^1\.\.(\d+)")


class TAPParser:
    """Parse TAP (Test Anything Protocol) format test results."""

    def parse(self, raw_bytes: bytes) -> ParsedArtifact:
        """Parse TAP bytes into a ParsedArtifact."""
        text = raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()
        cases: list[TestCase] = []

        for line in lines:
            line = line.strip()
            if not line or _PLAN_LINE.match(line):
                continue

            match = _TAP_LINE.match(line)
            if not match:
                continue

            ok_str, _num, description, directive, directive_msg = match.groups()
            is_ok = ok_str.lower() == "ok"
            directive = (directive or "").upper()

            if directive in ("SKIP", "TODO"):
                status = TestCaseStatus.SKIPPED
                message = directive_msg or directive
            elif is_ok:
                status = TestCaseStatus.PASSED
                message = ""
            else:
                status = TestCaseStatus.FAILED
                message = description or "test failed"

            cases.append(
                TestCase(
                    name=description.strip() if description else f"test {_num}",
                    status=status,
                    message=message,
                )
            )

        total = len(cases)
        failed = sum(1 for c in cases if c.status == TestCaseStatus.FAILED)
        skipped = sum(1 for c in cases if c.status == TestCaseStatus.SKIPPED)
        passed = total - failed - skipped

        suite = TestSuite(
            name="TAP",
            tests=tuple(cases),
            total=total,
            passed=passed,
            failed=failed,
            errors=0,
            skipped=skipped,
        )

        return ParsedArtifact(
            suites=(suite,),
            total=total,
            passed=passed,
            failed=failed,
            errors=0,
            skipped=skipped,
        )
