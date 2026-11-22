"""Shared fixtures for evaluation tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def eval_cases() -> list[dict]:
    path = Path(__file__).parent / "datasets" / "eval_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session", autouse=True)
async def initialize_retriever():
    """Ensure the RAG retriever is initialized before knowledge-based eval tests."""
    from app.core.config import get_settings
    from rag.ingest import run_ingest

    settings = get_settings()
    await run_ingest(settings, force=True)
