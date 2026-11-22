from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_SKIP_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuditMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        if method in _SKIP_METHODS:
            await self.app(scope, receive, send)
            return

        response_status: list[int] = []

        async def send_capture(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                response_status.append(message.get("status", 0))
            await send(message)

        await self.app(scope, receive, send_capture)

        await self._write_audit(scope, method, response_status)

    async def _write_audit(
        self,
        scope: dict[str, Any],
        method: str,
        response_status: list[int],
    ) -> None:
        try:
            from app.core.database import get_session
            from app.models.entities import AuditLog

            path = scope.get("path", "")
            state = scope.get("state", {})
            request_id: str | None = state.get("request_id")
            user: dict[str, Any] | None = state.get("user")

            client = scope.get("client")
            ip_address: str | None = client[0] if client else None

            actor_id: str | None = None
            actor_role: str | None = None
            if user:
                actor_id = user.get("sub")
                actor_role = user.get("role")

            status_code = response_status[0] if response_status else 0
            resource_type = _resource_type_from_path(path)

            log_entry = AuditLog(
                id=str(uuid4()),
                actor_id=actor_id,
                actor_role=actor_role,
                action=method,
                resource_type=resource_type,
                resource_id=None,
                request_id=request_id,
                ip_address=ip_address,
                extra={"path": path, "status_code": status_code},
            )

            async with get_session() as session:
                session.add(log_entry)
                await session.commit()
        except Exception:
            logger.debug("Audit write failed; continuing", exc_info=True)


def _resource_type_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    for part in parts:
        if part not in {"api", "v1"}:
            return part
    return "unknown"
