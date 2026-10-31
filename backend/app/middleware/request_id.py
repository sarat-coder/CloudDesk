from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from app.core.logging import log_context


_REQUEST_ID_HEADER = b"x-request-id"
_REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
ASGIApp = Callable[..., Awaitable[None]]


class RequestIdMiddleware:
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

        request_id = self._request_id_from(scope["headers"])
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _REQUEST_ID_HEADER
                ]
                headers.append((_REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        with log_context(request_id=request_id):
            await self.app(scope, receive, send_with_request_id)

    @staticmethod
    def _request_id_from(headers: list[tuple[bytes, bytes]]) -> str:
        for name, value in headers:
            if name.lower() == _REQUEST_ID_HEADER:
                try:
                    candidate = value.decode("ascii")
                except UnicodeDecodeError:
                    break
                if _REQUEST_ID_PATTERN.fullmatch(candidate):
                    return candidate
                break
        return str(uuid4())
