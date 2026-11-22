from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.redis import get_redis_client

_WINDOW_SECONDS = 60


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        settings = get_settings()
        limit = settings.rate_limit_per_minute

        redis = self._get_redis()
        key = f"rate:{client_ip}"
        try:
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, _WINDOW_SECONDS)
            if count > limit:
                response = JSONResponse(
                    {"detail": "Rate limit exceeded. Try again in a moment."},
                    status_code=429,
                )
                await response(scope, receive, send)
                return
        except Exception:
            pass

        await self.app(scope, receive, send)
