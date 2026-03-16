"""Artifact parsing domain models and protocols (REQ-010)."""

from lintel.domain.artifacts.models import (
    CoverageFile,
    CoverageReport,
    LineCoverage,
    ParsedArtifact,
    QualityGateResult,
    QualityGateRule,
    QualityGateSeverity,
    TestCase,
    TestCaseStatus,
    TestSuite,
)
from lintel.domain.artifacts.protocols import ArtifactParser, CoverageParser

__all__ = [
    "ArtifactParser",
    "CoverageFile",
    "CoverageParser",
    "CoverageReport",
    "LineCoverage",
    "ParsedArtifact",
    "QualityGateResult",
    "QualityGateRule",
    "QualityGateSeverity",
    "TestCase",
    "TestCaseStatus",
    "TestSuite",
]
