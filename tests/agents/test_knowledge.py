"""Tests for KnowledgeAgent — offline, in-memory vector store."""
from __future__ import annotations

import pytest

from agents.specialists.knowledge import KnowledgeAgent, _jaccard, _similar_cases
from app.schemas.workflow import Evidence, PreviousCase


class TestJaccard:
    def test_identical_sets_score_1(self) -> None:
        from agents.specialists.knowledge import _tokenize
        s = _tokenize("login sso saml")
        assert _jaccard(s, s) == 1.0

    def test_disjoint_sets_score_0(self) -> None:
        from agents.specialists.knowledge import _tokenize
        a = _tokenize("apple orange")
        b = _tokenize("cat dog fish")
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        from agents.specialists.knowledge import _tokenize
        a = _tokenize("login sso issue")
        b = _tokenize("login billing issue")
        score = _jaccard(a, b)
        assert 0 < score < 1

    def test_empty_sets_return_0(self) -> None:
        assert _jaccard(set(), set()) == 0.0


class TestSimilarCases:
    def test_similar_ticket_returned(self) -> None:
        history = [
            {"id": "t1", "ticket_number": "CD-100", "subject": "SSO login failing", "status": "resolved", "category": "login_issue", "created_at": "2024-01-01"},
            {"id": "t2", "ticket_number": "CD-101", "subject": "Storage quota exceeded", "status": "resolved", "category": "storage_quota", "created_at": "2024-01-02"},
        ]
        cases = _similar_cases("Cannot login via SSO", "SSO is not working", history)
        ids = [c.ticket_id for c in cases]
        assert "t1" in ids

    def test_unrelated_ticket_not_returned(self) -> None:
        history = [
            {"id": "t1", "ticket_number": "CD-100", "subject": "Dark mode request", "status": "resolved", "category": "feature_request", "created_at": "2024-01-01"},
        ]
        cases = _similar_cases("API rate limit 429 errors", "Our sync job is hitting 429", history)
        # Dark mode and API rate limit should not match
        ids = [c.ticket_id for c in cases]
        assert "t1" not in ids

    def test_returns_at_most_limit(self) -> None:
        history = [
            {"id": f"t{i}", "ticket_number": f"CD-{i}", "subject": "login sso issue", "status": "resolved", "category": "login_issue", "created_at": "2024-01-01"}
            for i in range(10)
        ]
        cases = _similar_cases("SSO login broken", "Cannot log in", history, limit=2)
        assert len(cases) <= 2


class TestKnowledgeAgent:
    async def test_returns_evidence_and_cases(self) -> None:
        agent = KnowledgeAgent()
        evidence, cases, usage, ms, calls = await agent.run(
            subject="Cannot login via SSO",
            body="SAML assertion is invalid",
            category="login_issue",
        )
        assert isinstance(evidence, list)
        assert isinstance(cases, list)

    async def test_tool_calls_contain_search_docs(self) -> None:
        agent = KnowledgeAgent()
        _, _, _, _, calls = await agent.run(
            subject="API rate limit",
            body="Getting 429 errors",
            category="api_failure",
        )
        tool_names = [c["tool"] for c in calls]
        assert "search_docs" in tool_names

    async def test_usage_always_zero(self) -> None:
        agent = KnowledgeAgent()
        _, _, usage, _, _ = await agent.run(
            subject="Storage full",
            body="Cannot upload files",
            category="storage_quota",
        )
        assert usage["total_tokens"] == 0

    async def test_similar_cases_found_from_history(self) -> None:
        history = [
            {
                "id": "t-sso", "ticket_number": "CD-999",
                "subject": "SSO login not working", "status": "resolved",
                "category": "login_issue", "created_at": "2024-01-01",
            }
        ]
        agent = KnowledgeAgent()
        _, cases, _, _, _ = await agent.run(
            subject="SSO login failing for all users",
            body="Cannot log in via SSO, authentication error",
            category="login_issue",
            ticket_history=history,
        )
        ids = [c.ticket_id for c in cases]
        assert "t-sso" in ids

    async def test_evidence_items_have_required_fields(self) -> None:
        agent = KnowledgeAgent()
        evidence, _, _, _, _ = await agent.run(
            subject="Billing refund",
            body="Please refund unused seats",
            category="billing",
        )
        for e in evidence:
            assert isinstance(e, Evidence)
            assert e.title is not None
