"""JUnit XML test result parser."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from lintel.domain.artifacts.models import (
    ParsedArtifact,
    TestCase,
    TestCaseStatus,
    TestSuite,
)


class JUnitXMLParser:
    """Parse JUnit XML format test results."""

    def parse(self, raw_bytes: bytes) -> ParsedArtifact:
        """Parse JUnit XML bytes into a ParsedArtifact."""
        root = ET.fromstring(raw_bytes)
        suites: list[TestSuite] = []

        if root.tag == "testsuites":
            for suite_elem in root.findall("testsuite"):
                suites.append(self._parse_suite(suite_elem))
        elif root.tag == "testsuite":
            suites.append(self._parse_suite(root))
        else:
            msg = f"Unexpected root element: {root.tag}"
            raise ValueError(msg)

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

    def _parse_suite(self, elem: ET.Element) -> TestSuite:
        """Parse a single <testsuite> element."""
        cases: list[TestCase] = []
        for tc_elem in elem.findall("testcase"):
            cases.append(self._parse_case(tc_elem))

        total = len(cases)
        failed = sum(1 for c in cases if c.status == TestCaseStatus.FAILED)
        errors_count = sum(1 for c in cases if c.status == TestCaseStatus.ERROR)
        skipped = sum(1 for c in cases if c.status == TestCaseStatus.SKIPPED)
        passed = total - failed - errors_count - skipped
        duration_ms = sum(c.duration_ms for c in cases)

        return TestSuite(
            name=elem.get("name", ""),
            tests=tuple(cases),
            total=total,
            passed=passed,
            failed=failed,
            errors=errors_count,
            skipped=skipped,
            duration_ms=duration_ms,
        )

    def _parse_case(self, elem: ET.Element) -> TestCase:
        """Parse a single <testcase> element."""
        status = TestCaseStatus.PASSED
        message = ""
        output = ""

        failure = elem.find("failure")
        error = elem.find("error")
        skip = elem.find("skipped")

        if failure is not None:
            status = TestCaseStatus.FAILED
            message = failure.get("message", "")
            output = failure.text or ""
        elif error is not None:
            status = TestCaseStatus.ERROR
            message = error.get("message", "")
            output = error.text or ""
        elif skip is not None:
            status = TestCaseStatus.SKIPPED
            message = skip.get("message", "")

        time_str = elem.get("time", "0")
        try:
            duration_ms = int(float(time_str) * 1000)
        except ValueError:
            duration_ms = 0

        return TestCase(
            name=elem.get("name", ""),
            classname=elem.get("classname", ""),
            status=status,
            duration_ms=duration_ms,
            message=message,
            output=output,
        )
