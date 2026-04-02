"""Tech stack discovery — automated detection of project technologies."""

from lintel.domain.techstack.discovery import TechStackDiscovery
from lintel.domain.techstack.types import (
    TechStackCategory,
    TechStackEntry,
    TechStackReport,
)

__all__ = [
    "TechStackCategory",
    "TechStackDiscovery",
    "TechStackEntry",
    "TechStackReport",
]
