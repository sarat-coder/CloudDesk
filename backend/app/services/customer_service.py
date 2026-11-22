from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Customer, CustomerMemory, Subscription, Ticket, Workspace
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customers import (
    CustomerDetailResponse,
    CustomerMemoryResponse,
    CustomerResponse,
    SubscriptionResponse,
    WorkspaceResponse,
)
from app.schemas.tickets import TicketSummaryResponse


def _ticket_summary(ticket: Ticket, customer_name: str | None = None) -> dict:
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "status": ticket.status,
        "severity": ticket.severity,
        "category": ticket.category,
        "customer_id": ticket.customer_id,
        "customer_name": customer_name,
        "channel": ticket.channel,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "escalation_required": False,
        "approval_status": "not_required",
    }


async def list_customers(
    session: AsyncSession,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CustomerResponse], int]:
    stmt = select(Customer)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Customer.name.ilike(like) | Customer.email.ilike(like))

    count_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar_one()

    stmt = stmt.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    customers = list(result.scalars().all())

    return [CustomerResponse.model_validate(c) for c in customers], total


async def get_customer_detail(
    session: AsyncSession, customer_id: str
) -> CustomerDetailResponse | None:
    repo = CustomerRepository(session)
    customer = await repo.get(customer_id)
    if customer is None:
        return None

    sub_result = await session.execute(
        select(Subscription).where(Subscription.customer_id == customer_id)
    )
    subscription = sub_result.scalars().first()

    ws_result = await session.execute(
        select(Workspace).where(Workspace.customer_id == customer_id)
    )
    workspace = ws_result.scalars().first()

    tickets_result = await session.execute(
        select(Ticket)
        .where(Ticket.customer_id == customer_id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = list(tickets_result.scalars().all())

    memory_result = await session.execute(
        select(CustomerMemory)
        .where(CustomerMemory.customer_id == customer_id)
        .order_by(CustomerMemory.created_at.desc())
    )
    memory_notes = list(memory_result.scalars().all())

    return CustomerDetailResponse(
        id=customer.id,
        external_id=customer.external_id,
        name=customer.name,
        email=customer.email,
        company=customer.company,
        plan=customer.plan,
        status=customer.status,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        subscription=SubscriptionResponse.model_validate(subscription) if subscription else None,
        workspace=WorkspaceResponse.model_validate(workspace) if workspace else None,
        tickets=[_ticket_summary(t, customer.name) for t in tickets],
        memory=[CustomerMemoryResponse.model_validate(m) for m in memory_notes],
    )
