"""Tests for ticketing integration domain model."""

from __future__ import annotations

import pytest

from lintel.domain.integrations.ticketing import (
    JiraAdapter,
    LinearAdapter,
    Ticket,
    TicketAdapter,
    TicketProvider,
    TicketStatus,
)


class TestTicketProvider:
    def test_values(self) -> None:
        assert TicketProvider.JIRA == "jira"
        assert TicketProvider.LINEAR == "linear"
        assert TicketProvider.GITHUB_ISSUES == "github_issues"

    def test_is_str(self) -> None:
        assert isinstance(TicketProvider.JIRA, str)


class TestTicketStatus:
    def test_all_statuses(self) -> None:
        expected = {"open", "in_progress", "in_review", "done", "closed"}
        assert {s.value for s in TicketStatus} == expected


class TestTicket:
    def test_frozen(self) -> None:
        ticket = Ticket(
            ticket_id="t1",
            provider=TicketProvider.JIRA,
            external_id="PROJ-1",
            project_key="PROJ",
            title="Test ticket",
        )
        with pytest.raises(AttributeError):
            ticket.title = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        ticket = Ticket(
            ticket_id="t1",
            provider=TicketProvider.LINEAR,
            external_id="LIN-1",
            project_key="PROJ",
            title="A ticket",
        )
        assert ticket.status == TicketStatus.OPEN
        assert ticket.assignee == ""
        assert ticket.labels == ()
        assert ticket.priority == "medium"
        assert ticket.description == ""
        assert ticket.url == ""


class TestTicketAdapterProtocol:
    def test_jira_is_adapter(self) -> None:
        assert isinstance(JiraAdapter(), TicketAdapter)

    def test_linear_is_adapter(self) -> None:
        assert isinstance(LinearAdapter(), TicketAdapter)


class TestJiraAdapter:
    @pytest.fixture()
    def adapter(self) -> JiraAdapter:
        return JiraAdapter(base_url="https://jira.example.com")

    async def test_create_ticket(self, adapter: JiraAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "My ticket", description="desc")
        assert ticket.provider == TicketProvider.JIRA
        assert ticket.project_key == "PROJ"
        assert ticket.title == "My ticket"
        assert ticket.external_id == "PROJ-1"
        assert "PROJ-1" in ticket.url

    async def test_get_ticket(self, adapter: JiraAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "T1")
        fetched = await adapter.get_ticket(ticket.external_id)
        assert fetched is not None
        assert fetched.ticket_id == ticket.ticket_id

    async def test_get_ticket_not_found(self, adapter: JiraAdapter) -> None:
        assert await adapter.get_ticket("NOPE") is None

    async def test_update_ticket(self, adapter: JiraAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "Original")
        updated = await adapter.update_ticket(
            ticket.external_id, title="Updated", status=TicketStatus.IN_PROGRESS
        )
        assert updated.title == "Updated"
        assert updated.status == TicketStatus.IN_PROGRESS

    async def test_update_ticket_not_found(self, adapter: JiraAdapter) -> None:
        with pytest.raises(KeyError):
            await adapter.update_ticket("NOPE", title="X")

    async def test_list_tickets(self, adapter: JiraAdapter) -> None:
        await adapter.create_ticket("PROJ", "T1")
        await adapter.create_ticket("PROJ", "T2")
        await adapter.create_ticket("OTHER", "T3")
        results = await adapter.list_tickets("PROJ")
        assert len(results) == 2

    async def test_list_tickets_filter_status(self, adapter: JiraAdapter) -> None:
        t = await adapter.create_ticket("PROJ", "T1")
        await adapter.update_ticket(t.external_id, status=TicketStatus.DONE)
        await adapter.create_ticket("PROJ", "T2")
        results = await adapter.list_tickets("PROJ", status=TicketStatus.DONE)
        assert len(results) == 1

    async def test_sync_status(self, adapter: JiraAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "T1")
        synced = await adapter.sync_status(ticket.external_id, TicketStatus.CLOSED)
        assert synced.status == TicketStatus.CLOSED


class TestLinearAdapter:
    @pytest.fixture()
    def adapter(self) -> LinearAdapter:
        return LinearAdapter(api_key="test-key")

    async def test_create_ticket(self, adapter: LinearAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "Linear ticket")
        assert ticket.provider == TicketProvider.LINEAR
        assert ticket.external_id == "LIN-1"
        assert "linear.app" in ticket.url

    async def test_update_ticket(self, adapter: LinearAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "Original")
        updated = await adapter.update_ticket(ticket.external_id, assignee="alice")
        assert updated.assignee == "alice"

    async def test_list_tickets_filter_assignee(self, adapter: LinearAdapter) -> None:
        t = await adapter.create_ticket("PROJ", "T1", assignee="alice")
        await adapter.create_ticket("PROJ", "T2", assignee="bob")
        results = await adapter.list_tickets("PROJ", assignee="alice")
        assert len(results) == 1
        assert results[0].external_id == t.external_id

    async def test_sync_status(self, adapter: LinearAdapter) -> None:
        ticket = await adapter.create_ticket("PROJ", "T1")
        synced = await adapter.sync_status(ticket.external_id, TicketStatus.IN_REVIEW)
        assert synced.status == TicketStatus.IN_REVIEW
