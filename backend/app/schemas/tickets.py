from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Category, Channel, Severity, TicketStatus


class TicketCreate(BaseModel):
    customer_id: str
    subject: str = Field(min_length=1, max_length=512)
    body: str = Field(min_length=1)
    channel: Channel = Channel.WEB


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    severity: Severity | None = None
    assigned_to: str | None = None


class TicketMessageResponse(BaseModel):
    id: str
    ticket_id: str
    role: str
    author_name: str | None = None
    body: str
    internal: bool = False
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketSummaryResponse(BaseModel):
    id: str
    ticket_number: str
    subject: str
    status: TicketStatus
    severity: Severity | None = None
    category: Category | None = None
    customer_id: str
    customer_name: str | None = None
    channel: Channel
    created_at: datetime
    updated_at: datetime
    escalation_required: bool = False
    approval_status: str = "not_required"

    model_config = {"from_attributes": True}


class TicketResponse(TicketSummaryResponse):
    body: str
    assigned_to: str | None = None
    resolved_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class TicketDetailResponse(TicketResponse):
    messages: list[TicketMessageResponse] = Field(default_factory=list)
    customer: dict[str, Any] | None = None
    subscription: dict[str, Any] | None = None
    history: list[TicketSummaryResponse] = Field(default_factory=list)
    workflow: dict[str, Any] | None = None
    resolution_actions: list[dict[str, Any]] = Field(default_factory=list)
    escalation: dict[str, Any] | None = None


class TicketListResponse(BaseModel):
    items: list[TicketSummaryResponse]
    total: int
    page: int
    page_size: int


class TicketReplyRequest(BaseModel):
    body: str = Field(min_length=1)
    internal: bool = False


class TicketRequestInfoRequest(BaseModel):
    questions: list[str] = Field(min_length=1)


class TicketEscalateRequest(BaseModel):
    reason: str = Field(min_length=1)
    priority: str = "normal"
