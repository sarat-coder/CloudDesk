"""EscalationAgent — decides whether the ticket must be escalated and to which team.

Nodes produced:
  risk_check   — assess_risk() helper (called by graph, not an agent method)
  escalation   — EscalationAgent.run() → EscalationDecision

Rules-plus-LLM pattern for escalation (§7.2):
  1. matching_escalation_rules() fires first — policy cases always escalate.
  2. LLM adds judgment in grey areas.
  3. If policy matched  → escalation_required = True, team = policy team.
  4. If LLM says escalate but severity is not high and confidence is low → distrust model,
     set escalation_required = False.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.prompts import SECURITY_PREAMBLE, wrap_untrusted
from agents.rules import matching_escalation_rules
from app.core.llm import call_structured
from app.schemas.workflow import (
    EscalationDecision,
    PlannedAction,
    ResolutionPlan,
)

logger = logging.getLogger(__name__)

_ESCALATE_PROMPT = """\
You are deciding whether a CloudDesk support ticket requires escalation to a specialist team.

Escalate when:
  - The issue involves billing disputes, payment fraud, or chargebacks.
  - There is a potential data breach, unauthorized access, or security incident.
  - There is confirmed or suspected data loss.
  - A GDPR erasure, account deletion, or compliance request is involved.
  - A legal, regulatory, or contractual issue is mentioned.
  - The issue is blocking an entire enterprise team with no workaround.

Do NOT escalate feature requests, common configuration issues, or minor billing questions.

Respond with JSON:
{
  "escalation_required": true | false,
  "reason": "<one sentence>",
  "team": "<team name or null>",
  "confidence": <0.0 to 1.0>
}
"""

_HIGH_CONFIDENCE_THRESHOLD = 0.7
_HIGH_SEVERITY = frozenset({"high", "critical"})


def assess_risk(
    planned_actions: list[PlannedAction],
    escalation_decision: EscalationDecision | None,
    severity: str,
    injection_flagged: bool,
    output_valid: bool,
) -> str:
    """Return 'high', 'medium', or 'low' risk for the workflow run.

    High risk blocks auto-execution and requires human review.
    """
    if injection_flagged:
        return "high"
    if not output_valid:
        return "high"
    if escalation_decision and escalation_decision.escalation_required:
        return "high"
    if severity == "critical":
        return "high"
    if any(a.requires_approval for a in planned_actions):
        return "high"
    if severity == "high":
        return "medium"
    return "low"


class EscalationAgent:
    """Stateless agent — determines whether escalation is required."""

    async def run(
        self,
        subject: str,
        body: str,
        severity: str,
        resolution_plan: ResolutionPlan | None,
    ) -> tuple[EscalationDecision, dict, float, list]:
        """Decide escalation. Policy rules always win over the model.

        Returns:
            decision, usage, duration_ms, tool_calls
        """
        text = f"{subject}\n\n{body}"
        plan_name = resolution_plan.summary if resolution_plan else ""

        # 1. Policy rules — always win
        matched_rules = matching_escalation_rules(text, plan_name)
        if matched_rules:
            rule = matched_rules[0]
            decision = EscalationDecision(
                escalation_required=True,
                reason=rule.reason,
                team=rule.team,
                confidence=1.0,
            )
            return decision, _zero_usage(), 0.0, []

        # 2. LLM judgment for grey areas
        decision, usage, ms, calls = await call_structured(
            EscalationDecision,
            [
                {"role": "system", "content": SECURITY_PREAMBLE + "\n\n" + _ESCALATE_PROMPT},
                {"role": "user", "content": wrap_untrusted(text)},
            ],
        )

        # 3. Distrust vague model escalations (§7.2)
        if (
            decision.escalation_required
            and severity not in _HIGH_SEVERITY
            and decision.confidence < _HIGH_CONFIDENCE_THRESHOLD
        ):
            decision = EscalationDecision(
                escalation_required=False,
                reason=f"Model suggested escalation but confidence {decision.confidence:.2f} is below threshold for {severity} severity",
                team=None,
                confidence=decision.confidence,
            )

        return decision, usage, ms, calls


def _zero_usage() -> dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
