"""Escalations endpoints — full wiring in Phase 10."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])


@router.get("")
async def list_escalations(
    status: str | None = Query(None),
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return []
