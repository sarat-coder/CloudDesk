"""Approval routes — approve or reject a pending workflow action.

§9 of CLAUDE.md:
  POST /api/v1/approvals/{id}/approve — approve the pending action, resume graph
  POST /api/v1/approvals/{id}/reject  — reject the pending action, route to escalation
  GET  /api/v1/approvals/{id}         — read the approval request

Requires 'agent' role.  Viewer gets 403.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.services import approval_service

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalResponse(BaseModel):
    id: str
    run_id: str | None
    ticket_id: str
    status: str
    reason: str | None
    decided_by: str | None


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    approval = await approval_service.get_pending_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return ApprovalResponse(
        id=approval.id,
        run_id=approval.run_id,
        ticket_id=approval.ticket_id,
        status=approval.status,
        reason=approval.reason,
        decided_by=approval.decided_by,
    )


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: str,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await approval_service.decide(
            db,
            approval_id=approval_id,
            approved=True,
            decided_by=user.get("sub", "unknown"),
        )
    except ValueError as exc:
        status_code = status.HTTP_409_CONFLICT if "already" in str(exc) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=str(exc))
    return result


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: str,
    user: dict = Depends(require_role("agent")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await approval_service.decide(
            db,
            approval_id=approval_id,
            approved=False,
            decided_by=user.get("sub", "unknown"),
        )
    except ValueError as exc:
        status_code = status.HTTP_409_CONFLICT if "already" in str(exc) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=str(exc))
    return result
