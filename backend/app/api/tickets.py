from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.schemas.tickets import (
    TicketCreate,
    TicketDetailResponse,
    TicketEscalateRequest,
    TicketListResponse,
    TicketMessageResponse,
    TicketReplyRequest,
    TicketRequestInfoRequest,
    TicketResponse,
    TicketSummaryResponse,
    TicketUpdate,
)
from app.services import ticket_service

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await ticket_service.list_tickets(
        db, status=status, severity=severity, search=search, page=page, page_size=page_size
    )
    return TicketListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
):
    try:
        ticket = await ticket_service.create_ticket(
            db,
            customer_id=body.customer_id,
            subject=body.subject,
            body=body.body,
            channel=body.channel.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        severity=ticket.severity,
        category=ticket.category,
        customer_id=ticket.customer_id,
        channel=ticket.channel,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await ticket_service.get_ticket_detail(db, ticket_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return detail


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def patch_ticket(
    ticket_id: str,
    body: TicketUpdate,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
):
    ticket = await ticket_service.update_ticket(
        db,
        ticket_id,
        status=body.status.value if body.status else None,
        severity=body.severity.value if body.severity else None,
        assigned_to=body.assigned_to,
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        severity=ticket.severity,
        category=ticket.category,
        customer_id=ticket.customer_id,
        channel=ticket.channel,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post("/{ticket_id}/reply", response_model=TicketMessageResponse)
async def reply_to_ticket(
    ticket_id: str,
    body: TicketReplyRequest,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
):
    msg = await ticket_service.add_reply(
        db,
        ticket_id,
        body=body.body,
        internal=body.internal,
        author_id=user.get("sub"),
    )
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketMessageResponse(
        id=msg.id,
        ticket_id=msg.ticket_id,
        role=msg.role,
        body=msg.body,
        created_at=msg.created_at,
    )


@router.post("/{ticket_id}/request-info", response_model=TicketMessageResponse)
async def request_info(
    ticket_id: str,
    body: TicketRequestInfoRequest,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
):
    msg = await ticket_service.add_request_info(
        db,
        ticket_id,
        questions=body.questions,
        author_id=user.get("sub"),
    )
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return TicketMessageResponse(
        id=msg.id,
        ticket_id=msg.ticket_id,
        role=msg.role,
        body=msg.body,
        created_at=msg.created_at,
    )


@router.post("/{ticket_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_workflow(
    ticket_id: str,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
):
    """Start the LangGraph workflow for this ticket (Phase 10)."""
    ticket = await ticket_service.get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.status == "waiting_on_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket is already waiting on approval",
        )
    return {"workflow_id": None, "status": "not_implemented_until_phase_10"}


@router.get("/{ticket_id}/workflow")
async def get_workflow(
    ticket_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest workflow state (Phase 9)."""
    ticket = await ticket_service.get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return {"workflow": None}


@router.get("/{ticket_id}/events")
async def get_events(
    ticket_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return workflow events for this ticket (Phase 9)."""
    ticket = await ticket_service.get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return []
