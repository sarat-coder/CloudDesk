"""Tests for CustomerAgent — offline, in-memory SQLite."""
from __future__ import annotations

import uuid

import pytest

from agents.specialists.customer import CustomerAgent
from app.schemas.workflow import CustomerContext


class TestCustomerAgent:
    async def test_returns_customer_context_type(self) -> None:
        agent = CustomerAgent()
        ctx, usage, ms, calls = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=str(uuid.uuid4()),
        )
        assert isinstance(ctx, CustomerContext)

    async def test_unknown_customer_returns_empty_context(self) -> None:
        agent = CustomerAgent()
        ctx, _, _, _ = await agent.run(
            customer_id="nonexistent-customer-id",
            ticket_id="nonexistent-ticket-id",
        )
        # Should not raise; just returns empty fields
        assert ctx.customer_id == "nonexistent-customer-id"
        assert ctx.name == ""

    async def test_load_errors_recorded_on_missing_customer(self) -> None:
        agent = CustomerAgent()
        ctx, _, _, _ = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=str(uuid.uuid4()),
        )
        # Either succeeds with empty data or records an error — never raises
        assert isinstance(ctx.load_errors, list)

    async def test_usage_always_zero(self) -> None:
        agent = CustomerAgent()
        _, usage, _, _ = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=str(uuid.uuid4()),
        )
        assert usage["total_tokens"] == 0
        assert usage["estimated_cost_usd"] == 0.0

    async def test_tool_calls_recorded(self) -> None:
        agent = CustomerAgent()
        _, _, _, calls = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=str(uuid.uuid4()),
        )
        tool_names = [c["tool"] for c in calls]
        assert "get_customer" in tool_names
        assert "get_ticket_history" in tool_names

    async def test_current_ticket_excluded_from_history(self) -> None:
        from app.core.database import create_tables
        await create_tables()

        agent = CustomerAgent()
        ticket_id = str(uuid.uuid4())
        ctx, _, _, _ = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=ticket_id,
        )
        # Current ticket must not appear in history
        for t in ctx.ticket_history:
            assert t.get("id") != ticket_id

    async def test_memory_notes_is_list(self) -> None:
        agent = CustomerAgent()
        ctx, _, _, _ = await agent.run(
            customer_id=str(uuid.uuid4()),
            ticket_id=str(uuid.uuid4()),
        )
        assert isinstance(ctx.memory_notes, list)
