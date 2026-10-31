from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_URL_PASSWORD = re.compile(r"(?<=//)([^/@]*):([^/@]*)@")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    demo_mode: bool = True
    environment: str = "development"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    jwt_secret: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr | None = None

    database_url: str = "sqlite+aiosqlite:///./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.db"
    redis_url: str = ""
    use_fake_redis: bool = False

    llm_provider: str = "fake"
    llm_api_key: SecretStr | None = None
    llm_model: str = "fake"

    embedding_provider: str = "fake"
    embedding_model: str = "fake"
    embedding_dimensions: int = Field(default=384, gt=0)

    vector_store: str = "memory"
    qdrant_url: str = ""
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "clouddesk_knowledge"

    approval_required_for_refunds: bool = True
    max_refund_without_approval: float = Field(default=0, ge=0)
    tool_timeout_seconds: float = Field(default=30, gt=0)
    rate_limit_per_minute: int = Field(default=120, gt=0)
    sample_data_dir: str = "sample_data"

    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "clouddesk-support"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError(
                        "CORS_ORIGINS must be a list or comma-separated string"
                    )
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("CORS_ORIGINS must be a list or comma-separated string")

    @property
    def effective_jwt_secret(self) -> str | None:
        for secret in (self.supabase_jwt_secret, self.jwt_secret):
            if secret is not None:
                value = secret.get_secret_value()
                if value:
                    return value
        return None

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        dumped = super().model_dump(**kwargs)
        for name in (
            "jwt_secret",
            "supabase_jwt_secret",
            "llm_api_key",
            "qdrant_api_key",
            "langchain_api_key",
        ):
            if dumped.get(name) is not None:
                dumped[name] = "**********"

        for name in ("database_url", "redis_url", "qdrant_url"):
            value = dumped.get(name)
            if isinstance(value, str):
                dumped[name] = _URL_PASSWORD.sub(r"\1:***@", value)
        return dumped


@lru_cache
def get_settings() -> Settings:
    return Settings()
