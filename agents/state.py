"""SupportState — the shared state bag passed through every graph node.

§7.3 of CLAUDE.md:
  - Every node returns a *partial* dict; LangGraph merges it into the state.
  - Reducers: errors and completed_nodes append (operator.add).
              token_usage sums via merge_usage.
  - Never put large documents into reducer fields.

The Annotated[…] reducer syntax is wired in agents/graph.py (Phase 10).
Here we define merge_usage and the TypedDict so specialists can be typed
without importing LangGraph directly.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.schemas.workflow import (
    Classification,
    CustomerContext,
    Diagnosis,
    EscalationDecision,
    Evidence,
    PlannedAction,
    PreviousCase,
    ResolutionPlan,
    SeverityAssessment,
)


def merge_usage(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Accumulate token usage across nodes."""
    return {
        "prompt_tokens": a.get("prompt_tokens", 0) + b.get("prompt_tokens", 0),
        "completion_tokens": a.get("completion_tokens", 0) + b.get("completion_tokens", 0),
        "total_tokens": a.get("total_tokens", 0) + b.get("total_tokens", 0),
        "estimated_cost_usd": round(
            a.get("estimated_cost_usd", 0.0) + b.get("estimated_cost_usd", 0.0), 8
        ),
    }


class SupportState(TypedDict, total=False):
    # ---- ticket input (set once at workflow start) ----
    ticket_id: str
    ticket_number: str
    subject: str
    body: str
    channel: str
    customer_id: str
    workflow_id: str

    # ---- injection flag (set by supervisor) ----
    injection_flagged: bool

    # ---- node outputs ----
    classification: Classification | None
    severity: str | None
    severity_reason: str | None
    customer_context: CustomerContext | None
    evidence: list[Evidence]
    previous_cases: list[PreviousCase]
    diagnosis: Diagnosis | None
    resolution_plan: ResolutionPlan | None
    planned_actions: list[PlannedAction]
    escalation_decision: EscalationDecision | None
    risk_level: str          # low / medium / high
    ticket_summary: str | None
    final_response: str | None

    # ---- reducers (Phase 10 will annotate these for LangGraph) ----
    errors: Annotated[list[str], operator.add]
    completed_nodes: Annotated[list[str], operator.add]
    token_usage: Annotated[dict[str, Any], merge_usage]

    # ---- progress ----
    current_node: str | None
