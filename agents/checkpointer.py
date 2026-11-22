"""LangGraph checkpointer factory.

Returns InMemorySaver when CHECKPOINT_DB_PATH=:memory: (tests),
otherwise AsyncSqliteSaver on the configured file path.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver


def get_checkpointer():
    """Return the appropriate LangGraph checkpointer based on settings."""
    from app.core.config import get_settings

    settings = get_settings()
    path = settings.checkpoint_db_path

    if path == ":memory:":
        return InMemorySaver()

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        return AsyncSqliteSaver.from_conn_string(path)
    except ImportError:
        # langgraph-checkpoint-sqlite not installed — fall back to in-memory
        return InMemorySaver()
