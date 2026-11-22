from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import Depends, FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
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

    if (
        settings.llm_provider == "fake"
        or settings.llm_api_key
        and settings.llm_api_key.get_secret_value()
    ):
        llm_ok = True
        llm_detail = ""
    else:
        llm_ok = False
        llm_detail = "LLM API key is not configured"

    results: dict[str, tuple[bool, str]] = {
        "database": (
            database_ok,
            ""
            if database_ok
            else "Database URL is missing or uses an unsupported driver",
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
        from app.core.database import create_tables
        await create_tables()
        if app_settings.demo_mode:
            from app.services.seed_service import bootstrap_demo_data
            await bootstrap_demo_data()
        try:
            from rag.ingest import run_ingest
            await run_ingest(app_settings)
        except Exception as exc:  # pragma: no cover — only fails if kb dir is missing
            import logging
            logging.getLogger(__name__).warning("Knowledge ingest skipped: %s", exc)
        yield

    api = FastAPI(
        title="CloudDesk",
        version=version("clouddesk"),
        lifespan=lifespan,
    )

    from app.api.approvals import router as approvals_router
    from app.api.auth import router as auth_router
    from app.api.customers import router as customers_router
    from app.api.dashboard import router as dashboard_router
    from app.api.escalations import router as escalations_router
    from app.api.knowledge import router as knowledge_router
    from app.api.settings import router as settings_router
    from app.api.tickets import router as tickets_router

    api.include_router(auth_router)
    api.include_router(tickets_router)
    api.include_router(approvals_router)
    api.include_router(customers_router)
    api.include_router(dashboard_router)
    api.include_router(escalations_router)
    api.include_router(knowledge_router)
    api.include_router(settings_router)

    from app.core.security import require_role

    @api.post("/api/v1/_test/agent-only")
    async def _test_agent_only(user: dict = Depends(require_role("agent"))) -> dict:
        return {"ok": True, "role": user["role"]}

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
    request_id_app = RequestIdMiddleware(cors_app)
    rate_limit_app = RateLimitMiddleware(request_id_app)
    return AuditMiddleware(rate_limit_app)


app = create_app()
