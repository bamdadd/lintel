"""Integration scanning submodule for the skills-api.

Provides scanners that detect integration patterns in Python source files
and tools to build dependency graphs and detect architectural antipatterns.
"""

from lintel.skills_api.integration_scanning.build_dependency_graph import (
    build_dependency_graph,
)
from lintel.skills_api.integration_scanning.detect_antipatterns import (
    detect_antipatterns,
)
from lintel.skills_api.integration_scanning.scan_async_integrations import (
    scan_async_integrations,
)
from lintel.skills_api.integration_scanning.scan_db_integrations import (
    scan_db_integrations,
)
from lintel.skills_api.integration_scanning.scan_external_api_calls import (
    scan_external_api_calls,
)
from lintel.skills_api.integration_scanning.scan_file_blob_integrations import (
    scan_file_blob_integrations,
)
from lintel.skills_api.integration_scanning.scan_sync_integrations import (
    scan_sync_integrations,
)

__all__ = [
    "build_dependency_graph",
    "detect_antipatterns",
    "scan_async_integrations",
    "scan_db_integrations",
    "scan_external_api_calls",
    "scan_file_blob_integrations",
    "scan_sync_integrations",
]
