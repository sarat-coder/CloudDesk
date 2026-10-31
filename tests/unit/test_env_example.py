from pathlib import Path

_REQUIRED_ENV_VARS = {
    "DEMO_MODE",
    "ENVIRONMENT",
    "CORS_ORIGINS",
    "JWT_SECRET",
    "SUPABASE_JWT_SECRET",
    "DATABASE_URL",
    "CHECKPOINT_DB_PATH",
    "REDIS_URL",
    "USE_FAKE_REDIS",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "VECTOR_STORE",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "APPROVAL_REQUIRED_FOR_REFUNDS",
    "MAX_REFUND_WITHOUT_APPROVAL",
    "TOOL_TIMEOUT_SECONDS",
    "RATE_LIMIT_PER_MINUTE",
    "SAMPLE_DATA_DIR",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
}


def test_env_example_documents_every_supported_environment_variable() -> None:
    env_file = Path(__file__).parents[2] / ".env.example"
    entries = {
        line.partition("=")[0]
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert entries == _REQUIRED_ENV_VARS


def test_env_example_uses_offline_safe_defaults_and_empty_credentials() -> None:
    env_file = Path(__file__).parents[2] / ".env.example"
    entries = {
        key: value
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, _, value in [line.partition("=")]
    }

    assert entries["DEMO_MODE"] == "true"
    assert entries["LLM_PROVIDER"] == "fake"
    assert entries["VECTOR_STORE"] == "memory"
    assert entries["USE_FAKE_REDIS"] == "true"
    assert entries["JWT_SECRET"] == ""
    assert entries["SUPABASE_JWT_SECRET"] == ""
    assert entries["LLM_API_KEY"] == ""
    assert entries["QDRANT_API_KEY"] == ""
    assert entries["LANGCHAIN_API_KEY"] == ""
