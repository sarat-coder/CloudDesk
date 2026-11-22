from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionResponse(BaseModel):
    id: str
    customer_id: str
    plan: str
    seats: int
    seats_used: int
    status: str
    billing_cycle: str
    amount: float
    currency: str
    renewal_date: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceResponse(BaseModel):
    id: str
    customer_id: str
    name: str
    slug: str
    region: str
    storage_used_gb: float
    storage_limit_gb: float
    member_count: int
    settings: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerResponse(BaseModel):
    id: str
    external_id: str
    name: str
    email: str
    company: str | None = None
    plan: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerMemoryResponse(BaseModel):
    id: str
    customer_id: str
    memory_type: str
    content: str
    source_ticket_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerDetailResponse(CustomerResponse):
    subscription: SubscriptionResponse | None = None
    workspace: WorkspaceResponse | None = None
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    memory: list[CustomerMemoryResponse] = Field(default_factory=list)


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
