"""Workflow schemas — Pydantic models for every agent output.

Every specialist agent returns exactly one of these models.  Agents must NOT
return free text; always use model_validate / call_structured (§18 rule 5).

§7.1 of CLAUDE.md lists the agent → schema mapping.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Category, Severity


# ---------------------------------------------------------------------------
# Supervisor agent schemas
# ---------------------------------------------------------------------------


class Classification(BaseModel):
    """Output of SupervisorAgent.understand_ticket."""
    category: Category = Category.OTHER
    summary: str = ""


class SeverityAssessment(BaseModel):
    """Output of SupervisorAgent.assess_severity."""
    severity: Severity = Severity.MEDIUM
    reason: str = ""


# ---------------------------------------------------------------------------
# Customer agent schemas
# ---------------------------------------------------------------------------


class CustomerContext(BaseModel):
    """Output of CustomerAgent.run — no LLM call."""
    customer_id: str = ""
    name: str = ""
    email: str = ""
    plan: str = ""
    subscription: dict[str, Any] | None = None
    workspace: dict[str, Any] | None = None
    ticket_history: list[dict[str, Any]] = Field(default_factory=list)
    memory_notes: list[dict[str, Any]] = Field(default_factory=list)
    load_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Knowledge agent schemas
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A single knowledge-base article chunk returned by KnowledgeAgent."""
    id: str = ""
    title: str = ""
    source: str = ""
    snippet: str = ""
    score: float = 0.0
    url: str = ""
    article_id: str = ""


class PreviousCase(BaseModel):
    """A similar previously-resolved ticket returned by KnowledgeAgent."""
    ticket_id: str = ""
    ticket_number: str = ""
    subject: str = ""
    status: str = ""
    category: str | None = None
    created_at: str = ""


# ---------------------------------------------------------------------------
# Troubleshooting agent schemas
# ---------------------------------------------------------------------------


class Diagnosis(BaseModel):
    """Output of TroubleshootingAgent.run."""
    probable_causes: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    active_incidents: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolution agent schemas
# ---------------------------------------------------------------------------


class PlannedAction(BaseModel):
    """A single tool call the resolution agent wants to execute."""
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    requires_approval: bool = False


class ResolutionPlan(BaseModel):
    """Output of ResolutionAgent.run."""
    summary: str = ""
    customer_reply: str = ""
    internal_notes: str = ""
    actions: list[PlannedAction] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Escalation agent schemas
# ---------------------------------------------------------------------------


class EscalationDecision(BaseModel):
    """Output of EscalationAgent.run."""
    escalation_required: bool = False
    reason: str = ""
    team: str | None = None
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# API response schema (used by /tickets/{id}/workflow endpoint)
# ---------------------------------------------------------------------------


class WorkflowStateResponse(BaseModel):
    workflow_id: str
    ticket_id: str
    status: str
    current_node: str | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    classification: dict[str, Any] | None = None
    severity: str | None = None
    severity_reason: str | None = None
    customer_context: dict[str, Any] | None = None
    retrieved_docs: list[dict[str, Any]] = Field(default_factory=list)
    previous_cases: list[dict[str, Any]] = Field(default_factory=list)
    diagnosis: dict[str, Any] | None = None
    resolution_plan: dict[str, Any] | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    risk: dict[str, Any] | None = None
    escalation_required: bool = False
    escalation_reason: str | None = None
    approval_status: str = "not_required"
    approval_request_id: str | None = None
    final_response: str | None = None
    ticket_summary: str | None = None
    errors: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    token_usage: dict[str, Any] = Field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
    )
