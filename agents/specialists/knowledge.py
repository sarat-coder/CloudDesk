"""KnowledgeAgent — retrieves cited evidence and finds similar previous cases.

Node produced: knowledge_retrieval → Evidence[], PreviousCase[]

Evidence comes from the RAG pipeline via the search_docs tool.
Similar cases are found with Jaccard overlap against ticket_history
from CustomerContext (no extra DB query needed).
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.workflow import Evidence, PreviousCase

logger = logging.getLogger(__name__)

_ZERO_USAGE: dict[str, Any] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "estimated_cost_usd": 0.0,
}

# Minimum Jaccard similarity to call a previous ticket "similar"
_JACCARD_THRESHOLD = 0.10


def _tokenize(text: str) -> set[str]:
    """Lowercase word-token set for Jaccard comparison.

    Strips punctuation and splits on underscores so 'login_issue' contributes
    both 'login' and 'issue', and 'SSO,' matches 'SSO'.
    """
    import re
    words = re.sub(r"[^\w\s]", " ", text.lower()).replace("_", " ").split()
    return set(w for w in words if len(w) > 1)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similar_cases(
    subject: str,
    body: str,
    ticket_history: list[dict[str, Any]],
    limit: int = 3,
) -> list[PreviousCase]:
    """Return up to *limit* resolved tickets similar to the current query."""
    query_tokens = _tokenize(f"{subject} {body}")
    scored: list[tuple[float, dict]] = []

    for t in ticket_history:
        t_tokens = _tokenize(f"{t.get('subject', '')} {t.get('category', '')}")
        score = _jaccard(query_tokens, t_tokens)
        if score >= _JACCARD_THRESHOLD:
            scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        PreviousCase(
            ticket_id=t.get("id", ""),
            ticket_number=t.get("ticket_number", ""),
            subject=t.get("subject", ""),
            status=t.get("status", ""),
            category=t.get("category"),
            created_at=t.get("created_at", ""),
        )
        for _, t in scored[:limit]
    ]


class KnowledgeAgent:
    """Stateless agent — retrieves documents from the knowledge base."""

    async def run(
        self,
        subject: str,
        body: str,
        category: str,
        ticket_history: list[dict[str, Any]] | None = None,
        top_k: int = 5,
    ) -> tuple[list[Evidence], list[PreviousCase], dict, float, list]:
        """Search the knowledge base and find similar previous cases.

        Returns:
            evidence, previous_cases, usage (always zero), duration_ms, tool_calls
        """
        import time

        from app.tools.registry import get_registry

        start = time.monotonic()
        registry = get_registry()
        tool_calls: list[dict] = []
        query = f"{subject} {body[:200]}"

        # --- search_docs ---
        r_docs = await registry.execute(
            "search_docs",
            {
                "query": query,
                "category": category,
                "top_k": top_k,
                "mode": "hybrid",
            },
        )
        tool_calls.append({"tool": "search_docs", "ok": r_docs.ok})

        evidence: list[Evidence] = []
        if r_docs.ok and r_docs.data:
            for item in r_docs.data.get("evidence", []):
                evidence.append(
                    Evidence(
                        id=item.get("id", ""),
                        title=item.get("title", ""),
                        source=item.get("source", ""),
                        snippet=item.get("snippet", ""),
                        score=float(item.get("score", 0.0)),
                        url=item.get("url", ""),
                        article_id=item.get("article_id", ""),
                    )
                )

        # --- similar cases via Jaccard ---
        previous_cases = _similar_cases(subject, body, ticket_history or [])

        duration_ms = (time.monotonic() - start) * 1000
        return evidence, previous_cases, dict(_ZERO_USAGE), duration_ms, tool_calls
