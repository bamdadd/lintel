"""Ticketing integration domain model.

Defines the provider enum, ticket dataclass, and adapter protocol
for Jira, Linear, and GitHub Issues integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class TicketProvider(StrEnum):
    """Supported external ticketing providers."""

    JIRA = "jira"
    LINEAR = "linear"
    GITHUB_ISSUES = "github_issues"


class TicketStatus(StrEnum):
    """Canonical ticket status mapped from provider-specific statuses."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CLOSED = "closed"


@dataclass(frozen=True)
class Ticket:
    """A ticket synchronised from an external ticketing provider."""

    ticket_id: str
    provider: TicketProvider
    external_id: str
    project_key: str
    title: str
    description: str = ""
    status: TicketStatus = TicketStatus.OPEN
    assignee: str = ""
    labels: tuple[str, ...] = ()
    priority: str = "medium"
    url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class TicketAdapter(Protocol):
    """Protocol for external ticketing system adapters."""

    async def create_ticket(
        self,
        project_key: str,
        title: str,
        description: str = "",
        labels: tuple[str, ...] = (),
        priority: str = "medium",
        assignee: str = "",
    ) -> Ticket:
        """Create a ticket in the external system."""
        ...

    async def update_ticket(
        self,
        external_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        labels: tuple[str, ...] | None = None,
        priority: str | None = None,
    ) -> Ticket:
        """Update a ticket in the external system."""
        ...

    async def get_ticket(self, external_id: str) -> Ticket | None:
        """Fetch a single ticket by its external ID."""
        ...

    async def list_tickets(
        self,
        project_key: str,
        *,
        status: TicketStatus | None = None,
        assignee: str | None = None,
    ) -> list[Ticket]:
        """List tickets for a project, optionally filtered."""
        ...

    async def sync_status(
        self,
        external_id: str,
        status: TicketStatus,
    ) -> Ticket:
        """Push a status update to the external system."""
        ...


class JiraAdapter:
    """Stubbed Jira adapter.

    Implements the TicketAdapter protocol with placeholder logic.
    Real implementation will use the Jira REST API.
    """

    def __init__(self, base_url: str = "", api_token: str = "") -> None:
        self.base_url = base_url
        self.api_token = api_token
        self._tickets: dict[str, Ticket] = {}

    async def create_ticket(
        self,
        project_key: str,
        title: str,
        description: str = "",
        labels: tuple[str, ...] = (),
        priority: str = "medium",
        assignee: str = "",
    ) -> Ticket:
        """Create a stub Jira ticket."""
        import uuid

        external_id = f"{project_key}-{len(self._tickets) + 1}"
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            provider=TicketProvider.JIRA,
            external_id=external_id,
            project_key=project_key,
            title=title,
            description=description,
            labels=labels,
            priority=priority,
            assignee=assignee,
            url=f"{self.base_url}/browse/{external_id}" if self.base_url else "",
        )
        self._tickets[external_id] = ticket
        return ticket

    async def update_ticket(
        self,
        external_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        labels: tuple[str, ...] | None = None,
        priority: str | None = None,
    ) -> Ticket:
        """Update a stub Jira ticket."""
        from dataclasses import replace

        existing = self._tickets.get(external_id)
        if existing is None:
            msg = f"Ticket {external_id} not found"
            raise KeyError(msg)
        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
        if assignee is not None:
            updates["assignee"] = assignee
        if labels is not None:
            updates["labels"] = labels
        if priority is not None:
            updates["priority"] = priority
        updated = replace(existing, **updates)
        self._tickets[external_id] = updated
        return updated

    async def get_ticket(self, external_id: str) -> Ticket | None:
        """Get a stub Jira ticket."""
        return self._tickets.get(external_id)

    async def list_tickets(
        self,
        project_key: str,
        *,
        status: TicketStatus | None = None,
        assignee: str | None = None,
    ) -> list[Ticket]:
        """List stub Jira tickets."""
        results = [t for t in self._tickets.values() if t.project_key == project_key]
        if status is not None:
            results = [t for t in results if t.status == status]
        if assignee is not None:
            results = [t for t in results if t.assignee == assignee]
        return results

    async def sync_status(
        self,
        external_id: str,
        status: TicketStatus,
    ) -> Ticket:
        """Sync status on a stub Jira ticket."""
        return await self.update_ticket(external_id, status=status)


class LinearAdapter:
    """Stubbed Linear adapter.

    Implements the TicketAdapter protocol with placeholder logic.
    Real implementation will use the Linear GraphQL API.
    """

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key
        self._tickets: dict[str, Ticket] = {}

    async def create_ticket(
        self,
        project_key: str,
        title: str,
        description: str = "",
        labels: tuple[str, ...] = (),
        priority: str = "medium",
        assignee: str = "",
    ) -> Ticket:
        """Create a stub Linear ticket."""
        import uuid

        external_id = f"LIN-{len(self._tickets) + 1}"
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            provider=TicketProvider.LINEAR,
            external_id=external_id,
            project_key=project_key,
            title=title,
            description=description,
            labels=labels,
            priority=priority,
            assignee=assignee,
            url=f"https://linear.app/issue/{external_id}",
        )
        self._tickets[external_id] = ticket
        return ticket

    async def update_ticket(
        self,
        external_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        labels: tuple[str, ...] | None = None,
        priority: str | None = None,
    ) -> Ticket:
        """Update a stub Linear ticket."""
        from dataclasses import replace

        existing = self._tickets.get(external_id)
        if existing is None:
            msg = f"Ticket {external_id} not found"
            raise KeyError(msg)
        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
        if assignee is not None:
            updates["assignee"] = assignee
        if labels is not None:
            updates["labels"] = labels
        if priority is not None:
            updates["priority"] = priority
        updated = replace(existing, **updates)
        self._tickets[external_id] = updated
        return updated

    async def get_ticket(self, external_id: str) -> Ticket | None:
        """Get a stub Linear ticket."""
        return self._tickets.get(external_id)

    async def list_tickets(
        self,
        project_key: str,
        *,
        status: TicketStatus | None = None,
        assignee: str | None = None,
    ) -> list[Ticket]:
        """List stub Linear tickets."""
        results = [t for t in self._tickets.values() if t.project_key == project_key]
        if status is not None:
            results = [t for t in results if t.status == status]
        if assignee is not None:
            results = [t for t in results if t.assignee == assignee]
        return results

    async def sync_status(
        self,
        external_id: str,
        status: TicketStatus,
    ) -> Ticket:
        """Sync status on a stub Linear ticket."""
        return await self.update_ticket(external_id, status=status)
