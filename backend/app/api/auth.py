from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.security import demo_login

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    result = demo_login(body.email)
    return TokenResponse(**result)
