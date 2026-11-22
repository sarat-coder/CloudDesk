"""Settings and introspection endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
async def get_app_settings(_user: dict = Depends(get_current_user)):
    settings = get_settings()
    return {
        "demo_mode": settings.demo_mode,
        "environment": settings.environment,
        "llm": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "api_key_configured": bool(
                settings.llm_api_key and settings.llm_api_key.get_secret_value()
            ),
            "tracing": settings.langchain_tracing_v2,
        },
        "vector_store": settings.vector_store,
        "redis": "fake" if settings.use_fake_redis else "real",
        "database": "sqlite" if "sqlite" in settings.database_url else "postgres",
        "approval_policy": {
            "refunds_require_approval": settings.approval_required_for_refunds,
            "max_refund_without_approval": settings.max_refund_without_approval,
            "approval_required_tools": ["create_refund_request", "reset_demo_setting"],
        },
    }
