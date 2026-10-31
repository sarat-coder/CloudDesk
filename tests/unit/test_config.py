from app.core.config import Settings, get_settings


def test_settings_load_environment_values(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("CORS_ORIGINS", "https://console.example, https://admin.example")

    settings = Settings(_env_file=None)

    assert settings.demo_mode is False
    assert settings.llm_provider == "openai"
    assert settings.cors_origins == [
        "https://console.example",
        "https://admin.example",
    ]


def test_settings_parse_json_origins_and_defaults(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://console.example"]')

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["https://console.example"]
    assert settings.demo_mode is True
    assert settings.llm_provider == "fake"


def test_settings_cached_factory_can_be_refreshed(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    try:
        assert get_settings().llm_provider == "anthropic"
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()


def test_settings_dump_redacts_secrets_and_url_passwords():
    settings = Settings(
        _env_file=None,
        jwt_secret="jwt-value",
        supabase_jwt_secret="supabase-value",
        llm_api_key="llm-value",
        qdrant_api_key="qdrant-value",
        langchain_api_key="langchain-value",
        database_url="postgresql+asyncpg://user:db-password@db.example/support",
        redis_url="redis://:redis-password@redis.example/0",
    )

    dumped = settings.model_dump()

    assert settings.effective_jwt_secret == "supabase-value"
    assert dumped["jwt_secret"] == "**********"
    assert dumped["supabase_jwt_secret"] == "**********"
    assert dumped["llm_api_key"] == "**********"
    assert dumped["qdrant_api_key"] == "**********"
    assert dumped["langchain_api_key"] == "**********"
    assert dumped["database_url"] == "postgresql+asyncpg://user:***@db.example/support"
    assert dumped["redis_url"] == "redis://:***@redis.example/0"
    assert "db-password" not in repr(dumped)
    assert "redis-password" not in repr(dumped)
