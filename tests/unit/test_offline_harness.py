from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest


@pytest.fixture(scope="session")
async def shared_async_value() -> AsyncIterator[str]:
    yield "available offline"


def test_offline_environment_is_configured_by_conftest() -> None:
    assert os.environ["DEMO_MODE"] == "true"
    assert os.environ["LLM_PROVIDER"] == "fake"
    assert os.environ["VECTOR_STORE"] == "memory"
    assert os.environ["USE_FAKE_REDIS"] == "true"
    assert os.environ["DATABASE_URL"].startswith("sqlite+aiosqlite:///")
    assert os.environ["CHECKPOINT_DB_PATH"] == ":memory:"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_role_header_fixtures_are_distinct_bearer_headers(
    agent_headers: dict[str, str],
    admin_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    values = {
        agent_headers["Authorization"],
        admin_headers["Authorization"],
        viewer_headers["Authorization"],
    }

    assert len(values) == 3
    assert all(value.startswith("Bearer test-") for value in values)


async def test_asyncio_is_configured_for_session_scoped_loop(
    shared_async_value: str,
) -> None:
    assert shared_async_value == "available offline"
