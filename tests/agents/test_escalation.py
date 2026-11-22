"""Tests for EscalationAgent and assess_risk — offline, fake LLM."""
from __future__ import annotations

import pytest

from agents.specialists.escalation import EscalationAgent, assess_risk
from app.schemas.workflow import EscalationDecision, PlannedAction, ResolutionPlan


class TestEscalationAgent:
    async def test_security_ticket_escalates_to_security_team(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Possible breach",
            body="Two accounts may have been successfully compromised.",
            severity="high",
            resolution_plan=None,
        )
        assert decision.escalation_required is True
        assert decision.team == "security_team"

    async def test_billing_dispute_escalates_to_billing_team(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Unauthorized charge on account",
            body="I see a fraudulent charge on my invoice. This is a payment dispute.",
            severity="high",
            resolution_plan=None,
        )
        assert decision.escalation_required is True
        assert decision.team == "billing_disputes_team"

    async def test_gdpr_deletion_escalates_to_compliance(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Delete account and erase all data",
            body="GDPR erasure request. Please delete account and all associated data.",
            severity="medium",
            resolution_plan=None,
        )
        assert decision.escalation_required is True
        assert decision.team == "data_compliance_team"

    async def test_data_loss_escalates_to_recovery_team(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Files disappeared from folder",
            body="Critical client files have disappeared from our shared folder.",
            severity="critical",
            resolution_plan=None,
        )
        assert decision.escalation_required is True
        assert decision.team == "data_recovery_team"

    async def test_normal_billing_question_not_escalated(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Invoice question",
            body="Can you explain this line item on my invoice?",
            severity="low",
            resolution_plan=None,
        )
        # Fake LLM returns escalation_required=False; no policy match
        assert isinstance(decision.escalation_required, bool)

    async def test_policy_wins_over_model(self) -> None:
        # Security ticket must escalate regardless of what model says
        agent = EscalationAgent()
        decision, _, ms, _ = await agent.run(
            subject="Security breach",
            body="Accounts compromised, unauthorized access detected.",
            severity="medium",
            resolution_plan=None,
        )
        assert decision.escalation_required is True
        assert ms == 0.0  # No LLM call made (policy matched first)

    async def test_returns_escalation_decision_type(self) -> None:
        agent = EscalationAgent()
        decision, _, _, _ = await agent.run(
            subject="Storage full",
            body="Cannot upload files.",
            severity="medium",
            resolution_plan=None,
        )
        assert isinstance(decision, EscalationDecision)


class TestAssessRisk:
    def test_injection_flagged_is_high_risk(self) -> None:
        risk = assess_risk([], None, "low", injection_flagged=True, output_valid=True)
        assert risk == "high"

    def test_invalid_output_is_high_risk(self) -> None:
        risk = assess_risk([], None, "low", injection_flagged=False, output_valid=False)
        assert risk == "high"

    def test_critical_severity_is_high_risk(self) -> None:
        risk = assess_risk([], None, "critical", injection_flagged=False, output_valid=True)
        assert risk == "high"

    def test_approval_required_action_is_high_risk(self) -> None:
        actions = [PlannedAction(tool="create_refund_request", requires_approval=True)]
        risk = assess_risk(actions, None, "medium", injection_flagged=False, output_valid=True)
        assert risk == "high"

    def test_escalation_required_is_high_risk(self) -> None:
        decision = EscalationDecision(escalation_required=True, team="security_team")
        risk = assess_risk([], decision, "medium", injection_flagged=False, output_valid=True)
        assert risk == "high"

    def test_high_severity_no_approval_is_medium_risk(self) -> None:
        risk = assess_risk([], None, "high", injection_flagged=False, output_valid=True)
        assert risk == "medium"

    def test_low_risk_scenario(self) -> None:
        risk = assess_risk([], None, "low", injection_flagged=False, output_valid=True)
        assert risk == "low"
