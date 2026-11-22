"""Short-term memory facade backed by Redis (or fakeredis in tests/demo).

Key patterns
------------
  conversation:{ticket_id}              — JSON list of messages         TTL 24 h
  workflow:{workflow_id}                — JSON dict of workflow state   TTL 24 h
  rag:{mode}:{category}:{top_k}:{hash} — JSON list of retrieval results TTL 300 s

§7.5 of CLAUDE.md.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

_CONVERSATION_TTL = 86_400   # 24 h
_WORKFLOW_TTL = 86_400        # 24 h
_CACHE_TTL = 300              # 5 min

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        from app.core.redis import get_redis_client
        _redis_client = get_redis_client()
    return _redis_client


def _query_hash(query: str) -> str:
    return hashlib.md5(query.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


def save_conversation(ticket_id: str, messages: list[dict[str, Any]]) -> None:
    """Persist the conversation history for a ticket."""
    _get_redis().set(
        f"conversation:{ticket_id}",
        json.dumps(messages),
        ex=_CONVERSATION_TTL,
    )


def load_conversation(ticket_id: str) -> list[dict[str, Any]]:
    """Return the conversation history for a ticket, or [] if none."""
    raw = _get_redis().get(f"conversation:{ticket_id}")
    if raw is None:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def append_message(ticket_id: str, message: dict[str, Any]) -> None:
    """Append one message to the existing conversation history."""
    messages = load_conversation(ticket_id)
    messages.append(message)
    save_conversation(ticket_id, messages)


# ---------------------------------------------------------------------------
# Workflow state
# ---------------------------------------------------------------------------


def save_workflow_state(workflow_id: str, state: dict[str, Any]) -> None:
    """Persist the latest workflow state snapshot."""
    _get_redis().set(
        f"workflow:{workflow_id}",
        json.dumps(state, default=str),
        ex=_WORKFLOW_TTL,
    )


def load_workflow_state(workflow_id: str) -> dict[str, Any] | None:
    """Return the workflow state snapshot, or None if not found."""
    raw = _get_redis().get(f"workflow:{workflow_id}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Retrieval cache
# ---------------------------------------------------------------------------


def _cache_key(mode: str, category: str, top_k: int, query: str) -> str:
    return f"rag:{mode}:{category}:{top_k}:{_query_hash(query)}"


def get_retrieval_cache(
    mode: str, category: str, top_k: int, query: str
) -> list[dict[str, Any]] | None:
    """Return cached retrieval results, or None on cache miss."""
    raw = _get_redis().get(_cache_key(mode, category, top_k, query))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def set_retrieval_cache(
    mode: str,
    category: str,
    top_k: int,
    query: str,
    results: list[dict[str, Any]],
) -> None:
    """Cache retrieval results for 5 minutes."""
    _get_redis().set(
        _cache_key(mode, category, top_k, query),
        json.dumps(results, default=str),
        ex=_CACHE_TTL,
    )


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def clear_ticket(ticket_id: str) -> None:
    """Remove conversation state for a ticket (called on close/resolve)."""
    _get_redis().delete(f"conversation:{ticket_id}")
