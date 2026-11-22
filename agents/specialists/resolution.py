"""ResolutionAgent — builds the resolution plan the agent will present to the human.

Node produced: resolution_planning → ResolutionPlan + list[PlannedAction]

Key design principles (§7.1, §7.4, §18):
  - plan_actions() is DETERMINISTIC: the LLM proposes prose; rules decide what
    tool calls are safe to plan.  The LLM cannot invent new action types.
  - _ground_response() verifies the customer reply references at least one
    knowledge article when evidence is available.
  - validate_customer_output() rejects replies containing internal URLs or
    secrets (N5); failure raises risk to 'high' upstream.
"""
from __future__ import annotations

import logging
from typing import Any

from agents.prompts import SECURITY_PREAMBLE, wrap_untrusted
import app.core.guardrails as _guardrails
from app.core.llm import call_structured
from app.schemas.workflow import (
    CustomerContext,
    Diagnosis,
    Evidence,
    PlannedAction,
    ResolutionPlan,
)

logger = logging.getLogger(__name__)

# Approval-gated tools (§7.4)
_APPROVAL_REQUIRED = frozenset({"create_refund_request", "reset_demo_setting"})

_PLAN_PROMPT = """\
You are a CloudDesk support specialist building a resolution plan for an agent.

Write a JSON object with these exact keys:
{
  "summary":        "<one paragraph — what the issue is and how it will be resolved>",
  "customer_reply": "<the reply to send to the customer — polite, cited from KB evidence>",
  "internal_notes": "<notes for the internal agent — do NOT include in customer reply>",
  "actions":        []
}

Rules for customer_reply:
  - Cite at least one KB article by title if evidence is provided.
  - Do not include internal URLs, secrets, pricing details, or other customers' data.
  - Keep it under 300 words.

The 'actions' field must be an empty list — actions are determined by policy, not the model.
"""


def plan_actions(
    category: str,
    customer_context: CustomerContext | None,
    diagnosis: Diagnosis | None,
    ticket_id: str,
) -> list[PlannedAction]:
    """Return the deterministic tool calls the workflow will execute.

    The list is derived from category + customer context — the LLM has no input.
    """
    actions: list[PlannedAction] = []

    # Always update the ticket status to in_progress
    actions.append(
        PlannedAction(
            tool="update_ticket",
            args={"ticket_id": ticket_id, "status": "in_progress"},
            description="Mark ticket as in-progress",
            requires_approval=False,
        )
    )

    # Billing category with subscription data → propose refund (approval required)
    if category == "billing" and customer_context and customer_context.subscription:
        sub = customer_context.subscription
        seats = sub.get("seats", 0)
        seats_used = sub.get("seats_used", 0)
        if seats > seats_used > 0:
            unused = seats - seats_used
            amount = round(sub.get("amount", 0.0) / max(seats, 1) * unused, 2)
            if amount > 0:
                actions.append(
                    PlannedAction(
                        tool="create_refund_request",
                        args={
                            "ticket_id": ticket_id,
                            "customer_id": customer_context.customer_id,
                            "amount": amount,
                            "currency": sub.get("currency", "USD"),
                            "reason": f"Refund for {unused} unused seat(s)",
                        },
                        description=f"Refund {amount} {sub.get('currency','USD')} for {unused} unused seat(s)",
                        requires_approval=True,
                    )
                )

    # Workspace permissions → propose settings reset (approval required)
    if category == "workspace_permissions" and customer_context and customer_context.workspace:
        ws_id = customer_context.workspace.get("id", "")
        if ws_id:
            actions.append(
                PlannedAction(
                    tool="reset_demo_setting",
                    args={
                        "workspace_id": ws_id,
                        "setting_key": "external_sharing_enabled",
                        "setting_value": True,
                    },
                    description="Enable external sharing in workspace settings",
                    requires_approval=True,
                )
            )

    return actions


def _ground_response(reply: str, evidence: list[Evidence]) -> bool:
    """Return True when the reply cites at least one KB article title.

    When evidence is empty the check is skipped (always passes).
    """
    if not evidence:
        return True
    reply_lower = reply.lower()
    return any(e.title.lower() in reply_lower for e in evidence)


class ResolutionAgent:
    """Stateless agent — builds the resolution plan presented to the human."""

    async def run(
        self,
        subject: str,
        body: str,
        category: str,
        severity: str,
        customer_context: CustomerContext | None,
        evidence: list[Evidence] | None,
        diagnosis: Diagnosis | None,
        ticket_id: str,
    ) -> tuple[ResolutionPlan, list[PlannedAction], bool, dict, float, list]:
        """Build a resolution plan and determine planned actions.

        Returns:
            plan, planned_actions, output_valid, usage, duration_ms, tool_calls
        """
        evidence = evidence or []

        # Build enriched context for the LLM
        evidence_text = "\n".join(
            f"  [{e.title}] ({e.url}): {e.snippet[:200]}" for e in evidence[:5]
        )
        diagnosis_text = ""
        if diagnosis:
            causes = "; ".join(diagnosis.probable_causes[:3])
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(diagnosis.steps[:5]))
            diagnosis_text = f"Probable causes: {causes}\nTroubleshooting steps:\n{steps}"

        customer_summary = ""
        if customer_context:
            customer_summary = (
                f"Customer: {customer_context.name} ({customer_context.plan} plan)"
            )

        user_content = (
            f"Ticket subject: {subject}\n"
            f"Category: {category}  |  Severity: {severity}\n"
            f"{customer_summary}\n\n"
            + (f"Knowledge base evidence:\n{evidence_text}\n\n" if evidence_text else "")
            + (f"Diagnosis:\n{diagnosis_text}\n\n" if diagnosis_text else "")
            + f"Ticket body:\n"
        ) + wrap_untrusted(body)

        plan, usage, ms, calls = await call_structured(
            ResolutionPlan,
            [
                {"role": "system", "content": SECURITY_PREAMBLE + "\n\n" + _PLAN_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        # Validate customer-facing reply (N5)
        is_valid, reason = _guardrails.validate_customer_output(plan.customer_reply)
        if not is_valid:
            logger.warning("Resolution plan failed output validation: %s", reason)
            plan = ResolutionPlan(
                summary=plan.summary,
                customer_reply=(
                    "Thank you for contacting CloudDesk support. "
                    "We are reviewing your case and will follow up shortly."
                ),
                internal_notes=f"{plan.internal_notes}\n[OUTPUT VALIDATION FAILED: {reason}]",
                actions=[],
            )

        # Grounding check
        if not _ground_response(plan.customer_reply, evidence):
            logger.info("Reply not grounded in KB evidence for ticket %s", ticket_id)

        # Deterministic action planning
        planned_actions = plan_actions(category, customer_context, diagnosis, ticket_id)

        return plan, planned_actions, is_valid, usage, ms, calls
