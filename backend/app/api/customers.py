from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.customers import CustomerDetailResponse, CustomerListResponse
from app.services import customer_service

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await customer_service.list_customers(db, search=search, page=page, page_size=page_size)
    return CustomerListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: str,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await customer_service.get_customer_detail(db, customer_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return detail
