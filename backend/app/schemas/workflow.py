"""Stub workflow schemas — implemented fully in Phase 9 and 10."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
