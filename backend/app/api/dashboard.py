"""Dashboard summary endpoint — full metrics wired in Phase 9."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import Ticket

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    open_result = await db.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.status.in_(["new", "in_progress", "waiting_on_customer", "waiting_on_approval"])
        )
    )
    open_tickets = open_result.scalar_one()

    resolved_result = await db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status == "resolved")
    )
    resolved_today = resolved_result.scalar_one()

    return {
        "open_tickets": open_tickets,
        "resolved_today": resolved_today,
        "pending_approvals": 0,
        "escalations_open": 0,
        "avg_resolution_minutes": None,
        "by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        "by_category": {},
        "recent_tickets": [],
        "agent_activity": [],
    }
