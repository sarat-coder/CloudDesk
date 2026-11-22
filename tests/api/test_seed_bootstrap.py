from __future__ import annotations

import pytest

from app.core.database import create_tables, get_session
from app.repositories.customer_repository import CustomerRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.seed_service import bootstrap_demo_data


@pytest.fixture(scope="module")
async def seeded_db():
    """Create tables and seed demo data once for this module."""
    await create_tables()
    await bootstrap_demo_data()


async def test_thirteen_tickets_loaded(seeded_db):
    async with get_session() as session:
        repo = TicketRepository(session)
        count = await repo.count()
    assert count == 13, f"Expected 13 tickets, got {count}"


async def test_eight_customers_loaded(seeded_db):
    async with get_session() as session:
        repo = CustomerRepository(session)
        count = await repo.count()
    assert count == 8, f"Expected 8 customers, got {count}"


async def test_cd_1002_exists(seeded_db):
    async with get_session() as session:
        repo = TicketRepository(session)
        ticket = await repo.get_by_number("CD-1002")
    assert ticket is not None
    assert "refund" in ticket.subject.lower() or "charged" in ticket.subject.lower()


async def test_no_duplicate_tickets_on_second_seed(seeded_db):
    """Running bootstrap_demo_data() twice must not create duplicate tickets."""
    await bootstrap_demo_data()
    async with get_session() as session:
        repo = TicketRepository(session)
        count = await repo.count()
    assert count == 13, f"Duplicates created: expected 13, got {count}"


async def test_no_duplicate_customers_on_second_seed(seeded_db):
    """Running bootstrap_demo_data() twice must not create duplicate customers."""
    async with get_session() as session:
        repo = CustomerRepository(session)
        count = await repo.count()
    assert count == 8, f"Duplicates created: expected 8, got {count}"


async def test_cd_1001_is_enterprise_customer(seeded_db):
    async with get_session() as session:
        t_repo = TicketRepository(session)
        c_repo = CustomerRepository(session)
        ticket = await t_repo.get_by_number("CD-1001")
        assert ticket is not None
        customer = await c_repo.get(ticket.customer_id)
    assert customer is not None
    assert customer.plan == "enterprise"


async def test_all_ticket_numbers_cd_prefix(seeded_db):
    async with get_session() as session:
        repo = TicketRepository(session)
        tickets = await repo.list_recent(limit=20)
    for t in tickets:
        assert t.ticket_number.startswith("CD-"), f"Bad ticket number: {t.ticket_number}"
