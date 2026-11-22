from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_ALGORITHM = "HS256"
_DEMO_EXPIRY_HOURS = 8

_ROLE_RANK: dict[str, int] = {
    "viewer": 1,
    "agent": 2,
    "admin": 3,
}

_DEMO_USERS: dict[str, dict[str, str]] = {
    "admin@clouddesk.demo": {
        "sub": "demo-admin-001",
        "role": "admin",
        "name": "Demo Admin",
    },
    "sam.agent@clouddesk.demo": {
        "sub": "demo-agent-001",
        "role": "agent",
        "name": "Sam Agent",
    },
    "vic.viewer@clouddesk.demo": {
        "sub": "demo-viewer-001",
        "role": "viewer",
        "name": "Vic Viewer",
    },
}

_bearer = HTTPBearer(auto_error=False)


def create_access_token(
    sub: str,
    role: str,
    name: str = "",
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    secret = settings.effective_jwt_secret
    if not secret:
        raise RuntimeError("JWT secret is not configured")

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=_DEMO_EXPIRY_HOURS)
    )
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "name": name,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.effective_jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
        )
    try:
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    request.state.user = payload
    return payload


def require_role(minimum_role: str):
    minimum_rank = _ROLE_RANK.get(minimum_role, 999)

    async def _check(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = user.get("role", "viewer")
        if _ROLE_RANK.get(role, 0) < minimum_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' cannot perform this action (requires '{minimum_role}')",
            )
        return user

    return _check


def demo_login(email: str) -> dict[str, str]:
    user = _DEMO_USERS.get(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown demo user",
        )
    token = create_access_token(
        sub=user["sub"],
        role=user["role"],
        name=user["name"],
    )
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}
