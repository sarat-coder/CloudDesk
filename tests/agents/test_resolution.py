"""Tests for ResolutionAgent and plan_actions — offline, fake LLM."""
from __future__ import annotations

import pytest

from agents.specialists.resolution import ResolutionAgent, plan_actions
from app.schemas.workflow import CustomerContext, Diagnosis, Evidence, ResolutionPlan


def _make_customer(plan: str = "pro", seats: int = 8, seats_used: int = 5) -> CustomerContext:
    return CustomerContext(
        customer_id="cust-test",
        name="Test User",
        email="test@example.com",
        plan=plan,
        subscription={
            "plan": plan, "seats": seats, "seats_used": seats_used,
            "amount": 80.0, "currency": "USD", "status": "active",
        },
        workspace={"id": "ws-test", "name": "TestWS", "slug": "testwsslug"},
    )


class TestPlanActions:
    def test_update_ticket_always_planned(self) -> None:
        actions = plan_actions("other", None, None, "ticket-123")
        tools = [a.tool for a in actions]
        assert "update_ticket" in tools

    def test_billing_with_unused_seats_plans_refund(self) -> None:
        ctx = _make_customer(seats=8, seats_used=5)
        actions = plan_actions("billing", ctx, None, "ticket-123")
        tools = [a.tool for a in actions]
        assert "create_refund_request" in tools

    def test_billing_refund_requires_approval(self) -> None:
        ctx = _make_customer(seats=8, seats_used=5)
        actions = plan_actions("billing", ctx, None, "ticket-123")
        refund = next(a for a in actions if a.tool == "create_refund_request")
        assert refund.requires_approval is True

    def test_billing_full_usage_no_refund(self) -> None:
        ctx = _make_customer(seats=5, seats_used=5)
        actions = plan_actions("billing", ctx, None, "ticket-123")
        tools = [a.tool for a in actions]
        assert "create_refund_request" not in tools

    def test_workspace_permissions_plans_reset(self) -> None:
        ctx = _make_customer()
        actions = plan_actions("workspace_permissions", ctx, None, "ticket-123")
        tools = [a.tool for a in actions]
        assert "reset_demo_setting" in tools

    def test_workspace_reset_requires_approval(self) -> None:
        ctx = _make_customer()
        actions = plan_actions("workspace_permissions", ctx, None, "ticket-123")
        reset = next((a for a in actions if a.tool == "reset_demo_setting"), None)
        assert reset is not None
        assert reset.requires_approval is True

    def test_no_actions_without_customer_context(self) -> None:
        actions = plan_actions("billing", None, None, "ticket-123")
        tools = [a.tool for a in actions]
        # update_ticket still planned; no refund without customer
        assert "update_ticket" in tools
        assert "create_refund_request" not in tools


class TestResolutionAgent:
    async def test_returns_plan_and_actions(self) -> None:
        agent = ResolutionAgent()
        plan, actions, valid, usage, ms, _ = await agent.run(
            subject="Billing refund",
            body="Charged 8 seats, using 5.",
            category="billing",
            severity="medium",
            customer_context=_make_customer(),
            evidence=[],
            diagnosis=None,
            ticket_id="ticket-test",
        )
        assert isinstance(plan, ResolutionPlan)
        assert isinstance(actions, list)

    async def test_billing_plans_refund_action(self) -> None:
        agent = ResolutionAgent()
        _, actions, _, _, _, _ = await agent.run(
            subject="Billing issue",
            body="Charged 8 seats, using 5.",
            category="billing",
            severity="medium",
            customer_context=_make_customer(seats=8, seats_used=5),
            evidence=[],
            diagnosis=None,
            ticket_id="ticket-test",
        )
        tools = [a.tool for a in actions]
        assert "create_refund_request" in tools

    async def test_plan_has_customer_reply(self) -> None:
        agent = ResolutionAgent()
        plan, _, _, _, _, _ = await agent.run(
            subject="Storage full",
            body="Cannot upload any files.",
            category="storage_quota",
            severity="medium",
            customer_context=None,
            evidence=[],
            diagnosis=None,
            ticket_id="ticket-test",
        )
        assert plan.customer_reply.strip()

    async def test_output_validation_flag_returned(self) -> None:
        agent = ResolutionAgent()
        _, _, output_valid, _, _, _ = await agent.run(
            subject="API issue",
            body="Getting errors.",
            category="api_failure",
            severity="low",
            customer_context=None,
            evidence=[],
            diagnosis=None,
            ticket_id="ticket-test",
        )
        assert isinstance(output_valid, bool)

    async def test_internal_url_in_reply_blocked(self, monkeypatch) -> None:
        import app.core.guardrails as guardrails

        def _mock_validate(text, current_customer_id=None):
            return False, "Internal URL detected"

        # Patch on the module that resolution.py imports as _guardrails
        monkeypatch.setattr(guardrails, "validate_customer_output", _mock_validate)

        agent = ResolutionAgent()
        plan, _, valid, _, _, _ = await agent.run(
            subject="Some ticket",
            body="Some body.",
            category="other",
            severity="low",
            customer_context=None,
            evidence=[],
            diagnosis=None,
            ticket_id="t-test",
        )
        assert valid is False
        assert "Thank you for contacting CloudDesk" in plan.customer_reply
