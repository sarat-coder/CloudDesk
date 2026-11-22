from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    ApprovalRequest,
    Customer,
    Escalation,
    Subscription,
    Ticket,
    TicketMessage,
    Workspace,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.ticket_repository import TicketMessageRepository, TicketRepository
from app.schemas.customers import CustomerResponse, SubscriptionResponse, WorkspaceResponse
from app.schemas.tickets import (
    TicketDetailResponse,
    TicketMessageResponse,
    TicketSummaryResponse,
)


def _ticket_to_summary(ticket: Ticket, customer_name: str | None = None) -> TicketSummaryResponse:
    return TicketSummaryResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        status=ticket.status,
        severity=ticket.severity,
        category=ticket.category,
        customer_id=ticket.customer_id,
        customer_name=customer_name,
        channel=ticket.channel,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _message_to_response(msg: TicketMessage) -> TicketMessageResponse:
    return TicketMessageResponse(
        id=msg.id,
        ticket_id=msg.ticket_id,
        role=msg.role,
        body=msg.body,
        created_at=msg.created_at,
    )


async def create_ticket(
    session: AsyncSession,
    customer_id: str,
    subject: str,
    body: str,
    channel: str,
) -> Ticket:
    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get(customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id!r} not found")

    repo = TicketRepository(session)
    count_result = await session.execute(select(func.count()).select_from(Ticket))
    n = (count_result.scalar_one() or 0) + 1
    ticket_number = f"CD-{1000 + n}"
    # Ensure uniqueness in case of collision
    while await repo.exists_by_number(ticket_number):
        n += 1
        ticket_number = f"CD-{1000 + n}"

    ticket = Ticket(
        id=str(uuid.uuid4()),
        ticket_number=ticket_number,
        customer_id=customer_id,
        subject=subject,
        body=body,
        channel=channel,
        status="new",
    )
    ticket = await repo.create(ticket)

    msg_repo = TicketMessageRepository(session)
    await msg_repo.create(
        TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            role="customer",
            body=body,
        )
    )
    return ticket


async def get_ticket(session: AsyncSession, ticket_id: str) -> Ticket | None:
    repo = TicketRepository(session)
    return await repo.get(ticket_id)


async def get_ticket_by_number(session: AsyncSession, ticket_number: str) -> Ticket | None:
    repo = TicketRepository(session)
    return await repo.get_by_number(ticket_number)


async def list_tickets(
    session: AsyncSession,
    status: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TicketSummaryResponse], int]:
    stmt = select(Ticket, Customer).join(Customer, Ticket.customer_id == Customer.id)

    if status:
        stmt = stmt.where(Ticket.status == status)
    if severity:
        stmt = stmt.where(Ticket.severity == severity)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            Ticket.subject.ilike(like) | Ticket.ticket_number.ilike(like)
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(Ticket.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(stmt)
    rows = result.all()

    items = [
        _ticket_to_summary(ticket, customer.name)
        for ticket, customer in rows
    ]
    return items, total


async def get_ticket_detail(
    session: AsyncSession, ticket_id: str
) -> TicketDetailResponse | None:
    repo = TicketRepository(session)
    ticket = await repo.get(ticket_id)
    if ticket is None:
        return None

    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get(ticket.customer_id)

    msg_repo = TicketMessageRepository(session)
    messages = await msg_repo.list_by_ticket(ticket_id)

    history: list[TicketSummaryResponse] = []
    if customer:
        past = await repo.list_by_customer(customer.id)
        history = [
            _ticket_to_summary(t, customer.name)
            for t in past
            if t.id != ticket_id
        ]

    sub_result = await session.execute(
        select(Subscription).where(Subscription.customer_id == ticket.customer_id)
    )
    subscription = sub_result.scalars().first()

    ws_result = await session.execute(
        select(Workspace).where(Workspace.customer_id == ticket.customer_id)
    )
    workspace = ws_result.scalars().first()

    escalation_result = await session.execute(
        select(Escalation).where(Escalation.ticket_id == ticket_id)
    )
    escalation = escalation_result.scalars().first()

    customer_name = customer.name if customer else None

    return TicketDetailResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        severity=ticket.severity,
        category=ticket.category,
        customer_id=ticket.customer_id,
        customer_name=customer_name,
        channel=ticket.channel,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[_message_to_response(m) for m in messages],
        customer=CustomerResponse.model_validate(customer).model_dump() if customer else None,
        subscription=SubscriptionResponse.model_validate(subscription).model_dump() if subscription else None,
        history=history,
        workflow=None,
        resolution_actions=[],
        escalation=None,
    )


async def update_ticket(
    session: AsyncSession,
    ticket_id: str,
    status: str | None = None,
    severity: str | None = None,
    assigned_to: str | None = None,
) -> Ticket | None:
    repo = TicketRepository(session)
    ticket = await repo.get(ticket_id)
    if ticket is None:
        return None

    kwargs: dict = {}
    if status is not None:
        kwargs["status"] = status
    if severity is not None:
        kwargs["severity"] = severity
    if assigned_to is not None:
        kwargs["assigned_to"] = assigned_to

    if kwargs:
        ticket = await repo.update(ticket, **kwargs)

    return ticket


async def add_reply(
    session: AsyncSession,
    ticket_id: str,
    body: str,
    internal: bool = False,
    author_id: str | None = None,
) -> TicketMessage | None:
    repo = TicketRepository(session)
    ticket = await repo.get(ticket_id)
    if ticket is None:
        return None

    msg_repo = TicketMessageRepository(session)
    msg = await msg_repo.create(
        TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            role="agent",
            body=body,
            author_id=author_id,
        )
    )
    return msg


async def add_request_info(
    session: AsyncSession,
    ticket_id: str,
    questions: list[str],
    author_id: str | None = None,
) -> TicketMessage | None:
    repo = TicketRepository(session)
    ticket = await repo.get(ticket_id)
    if ticket is None:
        return None

    body = "\n".join(f"- {q}" for q in questions)
    msg_repo = TicketMessageRepository(session)
    msg = await msg_repo.create(
        TicketMessage(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            role="agent",
            body=body,
            author_id=author_id,
        )
    )
    await repo.update(ticket, status="waiting_on_customer")
    return msg
