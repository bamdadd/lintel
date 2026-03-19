"""coverage.py JSON report parser."""

from __future__ import annotations

import json
from typing import Any

from lintel.domain.artifacts.models import CoverageFile, CoverageReport, LineCoverage


class CoveragePyParser:
    """Parse coverage.py JSON format reports."""

    def parse(self, raw_bytes: bytes) -> CoverageReport:
        """Parse coverage.py JSON bytes into a CoverageReport."""
        data: dict[str, Any] = json.loads(raw_bytes)

        files: list[CoverageFile] = []
        file_data = data.get("files", {})

        for path, info in file_data.items():
            if not isinstance(info, dict):
                continue

            summary = info.get("summary", {})
            executed_lines: list[int] = info.get("executed_lines", [])
            missing_lines: list[int] = info.get("missing_lines", [])

            all_lines = sorted(set(executed_lines) | set(missing_lines))
            line_coverages: list[LineCoverage] = []
            for ln in all_lines:
                hit = 1 if ln in executed_lines else 0
                line_coverages.append(LineCoverage(line_number=ln, hit_count=hit))

            lines_covered = summary.get(
                "covered_lines",
                len(executed_lines),
            )
            lines_total = summary.get(
                "num_statements",
                len(all_lines),
            )
            branches_covered = summary.get("covered_branches", 0)
            branches_total = summary.get("num_branches", 0)

            files.append(
                CoverageFile(
                    path=path,
                    lines=tuple(line_coverages),
                    lines_covered=lines_covered,
                    lines_total=lines_total,
                    branches_covered=branches_covered,
                    branches_total=branches_total,
                )
            )

        totals = data.get("totals", {})
        total_lines_covered = totals.get(
            "covered_lines",
            sum(f.lines_covered for f in files),
        )
        total_lines = totals.get(
            "num_statements",
            sum(f.lines_total for f in files),
        )
        total_branches_covered = totals.get(
            "covered_branches",
            sum(f.branches_covered for f in files),
        )
        total_branches = totals.get(
            "num_branches",
            sum(f.branches_total for f in files),
        )

        line_rate = total_lines_covered / total_lines if total_lines > 0 else 0.0
        branch_rate = total_branches_covered / total_branches if total_branches > 0 else 0.0

        return CoverageReport(
            files=tuple(files),
            line_rate=line_rate,
            branch_rate=branch_rate,
            lines_covered=total_lines_covered,
            lines_total=total_lines,
            branches_covered=total_branches_covered,
            branches_total=total_branches,
        )
