from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.middleware.request_id import RequestIdMiddleware


def _readiness_checks(settings: Settings) -> dict[str, dict[str, str]]:
    database_scheme = settings.database_url.partition(":")[0].lower()
    database_ok = database_scheme in {"sqlite+aiosqlite", "postgresql+asyncpg"}

    redis_ok = bool(settings.redis_url) or settings.demo_mode or settings.use_fake_redis

    if settings.vector_store == "memory":
        vector_store_ok = True
        vector_store_detail = ""
    elif settings.vector_store == "qdrant":
        vector_store_ok = settings.qdrant_url.startswith(("http://", "https://"))
        vector_store_detail = "Qdrant URL is not configured"
    else:
        vector_store_ok = False
        vector_store_detail = "Vector store provider is unsupported"

    if settings.llm_provider == "fake":
        llm_ok = True
        llm_detail = ""
    elif settings.llm_api_key and settings.llm_api_key.get_secret_value():
        llm_ok = True
        llm_detail = ""
    else:
        llm_ok = False
        llm_detail = "LLM API key is not configured"

    results: dict[str, tuple[bool, str]] = {
        "database": (
            database_ok,
            "" if database_ok else "Database URL is missing or uses an unsupported driver",
        ),
        "redis": (
            redis_ok,
            "" if redis_ok else "Redis URL is not configured",
        ),
        "vector_store": (vector_store_ok, vector_store_detail),
        "llm": (llm_ok, llm_detail),
    }
    return {
        name: {
            "status": "ok" if is_ready else "error",
            **({"detail": detail} if detail else {}),
        }
        for name, (is_ready, detail) in results.items()
    }


def create_app(settings: Settings | None = None) -> ASGIApp:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        setup_logging()
        yield

    api = FastAPI(
        title="CloudDesk",
        version=version("clouddesk"),
        lifespan=lifespan,
    )

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "clouddesk",
            "version": api.version,
            "environment": app_settings.environment,
        }

    @api.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @api.get("/health/ready")
    async def ready() -> JSONResponse:
        checks = _readiness_checks(app_settings)
        status = (
            "ready"
            if all(check["status"] == "ok" for check in checks.values())
            else "degraded"
        )
        return JSONResponse(
            content={"status": status, "checks": checks},
            status_code=200 if status == "ready" else 503,
        )

    cors_app = CORSMiddleware(
        app=api,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    return RequestIdMiddleware(cors_app)


app = create_app()
