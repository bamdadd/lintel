"""LCOV coverage report parser."""

from __future__ import annotations

import contextlib

from lintel.domain.artifacts.models import CoverageFile, CoverageReport, LineCoverage


class LCOVParser:
    """Parse LCOV/geninfo format coverage reports."""

    def parse(self, raw_bytes: bytes) -> CoverageReport:
        """Parse LCOV bytes into a CoverageReport."""
        text = raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()

        files: list[CoverageFile] = []
        current_path = ""
        current_lines: list[LineCoverage] = []
        lines_covered = 0
        lines_total = 0
        branches_covered = 0
        branches_total = 0

        for line in lines:
            line = line.strip()
            if line.startswith("SF:"):
                current_path = line[3:]
                current_lines = []
                lines_covered = 0
                lines_total = 0
                branches_covered = 0
                branches_total = 0
            elif line.startswith("DA:"):
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    try:
                        line_num = int(parts[0])
                        hit_count = int(parts[1])
                        current_lines.append(
                            LineCoverage(line_number=line_num, hit_count=hit_count)
                        )
                        lines_total += 1
                        if hit_count > 0:
                            lines_covered += 1
                    except ValueError:
                        pass
            elif line.startswith("LH:"):
                with contextlib.suppress(ValueError):
                    lines_covered = int(line[3:])
            elif line.startswith("LF:"):
                with contextlib.suppress(ValueError):
                    lines_total = int(line[3:])
            elif line.startswith("BRH:"):
                with contextlib.suppress(ValueError):
                    branches_covered = int(line[4:])
            elif line.startswith("BRF:"):
                with contextlib.suppress(ValueError):
                    branches_total = int(line[4:])
            elif line == "end_of_record":
                files.append(
                    CoverageFile(
                        path=current_path,
                        lines=tuple(current_lines),
                        lines_covered=lines_covered,
                        lines_total=lines_total,
                        branches_covered=branches_covered,
                        branches_total=branches_total,
                    )
                )
                current_path = ""
                current_lines = []

        total_lines_covered = sum(f.lines_covered for f in files)
        total_lines = sum(f.lines_total for f in files)
        total_branches_covered = sum(f.branches_covered for f in files)
        total_branches = sum(f.branches_total for f in files)

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
