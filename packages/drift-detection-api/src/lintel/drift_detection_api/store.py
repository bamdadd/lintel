"""In-memory stores for drift detection entities."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.domain.types import DriftAlert, DriftRule, DriftScan


class InMemoryDriftRuleStore:
    """Simple in-memory store for drift rules."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def add(self, rule: DriftRule) -> dict[str, Any]:
        data = asdict(rule)
        self._items[rule.rule_id] = data
        return data

    async def get(self, rule_id: str) -> dict[str, Any] | None:
        return self._items.get(rule_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._items.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [v for v in self._items.values() if v.get("project_id") == project_id]

    async def update(self, rule_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        item = self._items.get(rule_id)
        if item is None:
            return None
        item.update(updates)
        return item

    async def remove(self, rule_id: str) -> bool:
        return self._items.pop(rule_id, None) is not None


class InMemoryDriftAlertStore:
    """Simple in-memory store for drift alerts."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def add(self, alert: DriftAlert) -> dict[str, Any]:
        data = asdict(alert)
        self._items[alert.alert_id] = data
        return data

    async def get(self, alert_id: str) -> dict[str, Any] | None:
        return self._items.get(alert_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._items.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [v for v in self._items.values() if v.get("project_id") == project_id]

    async def update(self, alert_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        item = self._items.get(alert_id)
        if item is None:
            return None
        item.update(updates)
        return item

    async def remove(self, alert_id: str) -> bool:
        return self._items.pop(alert_id, None) is not None


class InMemoryDriftScanStore:
    """Simple in-memory store for drift scans."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def add(self, scan: DriftScan) -> dict[str, Any]:
        data = asdict(scan)
        self._items[scan.scan_id] = data
        return data

    async def get(self, scan_id: str) -> dict[str, Any] | None:
        return self._items.get(scan_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._items.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [v for v in self._items.values() if v.get("project_id") == project_id]

    async def update(self, scan_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        item = self._items.get(scan_id)
        if item is None:
            return None
        item.update(updates)
        return item

    async def remove(self, scan_id: str) -> bool:
        return self._items.pop(scan_id, None) is not None
