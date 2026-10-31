from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


_TEST_DATABASE_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="clouddesk-pytest-")
)
_TEST_DATABASE_PATH = _TEST_DATABASE_DIRECTORY / "support.db"

os.environ.update(
    {
        "DEMO_MODE": "true",
        "ENVIRONMENT": "test",
        "CORS_ORIGINS": "http://localhost:3000",
        "JWT_SECRET": "clouddesk-test-jwt-secret",
        "SUPABASE_JWT_SECRET": "clouddesk-test-supabase-jwt-secret",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TEST_DATABASE_PATH.as_posix()}",
        "CHECKPOINT_DB_PATH": ":memory:",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "USE_FAKE_REDIS": "true",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "unused-test-placeholder",
        "LLM_MODEL": "fake",
        "EMBEDDING_PROVIDER": "fake",
        "EMBEDDING_MODEL": "fake",
        "EMBEDDING_DIMENSIONS": "384",
        "VECTOR_STORE": "memory",
        "QDRANT_URL": "http://127.0.0.1:6333",
        "QDRANT_API_KEY": "unused-test-placeholder",
        "QDRANT_COLLECTION": "clouddesk_knowledge",
        "APPROVAL_REQUIRED_FOR_REFUNDS": "true",
        "MAX_REFUND_WITHOUT_APPROVAL": "0",
        "TOOL_TIMEOUT_SECONDS": "30",
        "RATE_LIMIT_PER_MINUTE": "120",
        "SAMPLE_DATA_DIR": "sample_data",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGCHAIN_API_KEY": "unused-test-placeholder",
        "LANGCHAIN_PROJECT": "clouddesk-support",
    }
)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_database_directory() -> Iterator[None]:
    yield
    shutil.rmtree(_TEST_DATABASE_DIRECTORY)


@pytest.fixture
def agent_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-agent-token"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-admin-token"}


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-viewer-token"}
