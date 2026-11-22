"""Unit tests for the memory package.

Covers:
  short_term — save/load conversation, workflow state, retrieval cache
  long_term  — add_note (scrub, dedup, type validation), recall (limit)
  memory_service — recall_customer, record_resolution (past_issue + steps + note)

Runs offline: fakeredis + in-memory SQLite (via conftest.py).
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

# Ensure project root is on sys.path before any app imports
_PROJECT_ROOT = str(__file__.replace("\\", "/").rsplit("/tests/", 1)[0])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# short_term tests (pure Redis, no DB)
# ---------------------------------------------------------------------------


class TestShortTermConversation:
    def _clear(self, ticket_id: str) -> None:
        from memory.short_term import clear_ticket
        clear_ticket(ticket_id)

    def test_load_missing_returns_empty_list(self) -> None:
        from memory.short_term import load_conversation
        result = load_conversation(f"nonexistent-{uuid.uuid4()}")
        assert result == []

    def test_save_and_load_roundtrip(self) -> None:
        from memory.short_term import load_conversation, save_conversation
        tid = f"t-{uuid.uuid4()}"
        messages = [{"role": "user", "content": "Hello"}]
        save_conversation(tid, messages)
        assert load_conversation(tid) == messages
        self._clear(tid)

    def test_append_message(self) -> None:
        from memory.short_term import append_message, load_conversation
        tid = f"t-{uuid.uuid4()}"
        append_message(tid, {"role": "user", "content": "first"})
        append_message(tid, {"role": "agent", "content": "second"})
        msgs = load_conversation(tid)
        assert len(msgs) == 2
        assert msgs[1]["content"] == "second"
        self._clear(tid)

    def test_clear_removes_conversation(self) -> None:
        from memory.short_term import clear_ticket, load_conversation, save_conversation
        tid = f"t-{uuid.uuid4()}"
        save_conversation(tid, [{"role": "user", "content": "hi"}])
        clear_ticket(tid)
        assert load_conversation(tid) == []


class TestShortTermWorkflowState:
    def test_missing_state_returns_none(self) -> None:
        from memory.short_term import load_workflow_state
        result = load_workflow_state(f"wf-{uuid.uuid4()}")
        assert result is None

    def test_save_and_load_state(self) -> None:
        from memory.short_term import load_workflow_state, save_workflow_state
        wid = f"wf-{uuid.uuid4()}"
        state = {"ticket_id": "CD-1001", "step": "classify"}
        save_workflow_state(wid, state)
        assert load_workflow_state(wid) == state

    def test_overwrite_state(self) -> None:
        from memory.short_term import load_workflow_state, save_workflow_state
        wid = f"wf-{uuid.uuid4()}"
        save_workflow_state(wid, {"step": "v1"})
        save_workflow_state(wid, {"step": "v2"})
        assert load_workflow_state(wid)["step"] == "v2"


class TestShortTermRetrievalCache:
    def test_cache_miss_returns_none(self) -> None:
        from memory.short_term import get_retrieval_cache
        result = get_retrieval_cache("hybrid", "billing", 5, f"q-{uuid.uuid4()}")
        assert result is None

    def test_cache_hit_returns_results(self) -> None:
        from memory.short_term import get_retrieval_cache, set_retrieval_cache
        query = f"q-{uuid.uuid4()}"
        results = [{"id": "art-1", "score": 0.9}]
        set_retrieval_cache("hybrid", "billing", 5, query, results)
        assert get_retrieval_cache("hybrid", "billing", 5, query) == results

    def test_different_query_is_cache_miss(self) -> None:
        from memory.short_term import get_retrieval_cache, set_retrieval_cache
        set_retrieval_cache("hybrid", "billing", 5, "query-A", [{"id": "1"}])
        assert get_retrieval_cache("hybrid", "billing", 5, "query-B") is None


# ---------------------------------------------------------------------------
# long_term tests (async DB)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    """Provide a live async SQLite session with tables created."""
    from app.core.database import get_session
    async with get_session() as session:
        # Ensure tables exist (idempotent)
        from app.core.database import create_tables
        await create_tables()
        yield session


@pytest.fixture
def customer_id() -> str:
    return str(uuid.uuid4())


class TestLongTermAddNote:
    async def test_add_and_recall_single_note(self, db_session, customer_id) -> None:
        from memory.long_term import add_note, recall
        note = await add_note(customer_id, "note", "Customer prefers email", db_session)
        assert note is not None
        assert note.content == "Customer prefers email"
        notes = await recall(customer_id, db_session)
        assert any(n.id == note.id for n in notes)

    async def test_duplicate_note_returns_none(self, db_session, customer_id) -> None:
        from memory.long_term import add_note
        content = "Same note content"
        first = await add_note(customer_id, "note", content, db_session)
        second = await add_note(customer_id, "note", content, db_session)
        assert first is not None
        assert second is None  # skipped as duplicate

    async def test_scrub_removes_secrets(self, db_session, customer_id) -> None:
        from memory.long_term import add_note
        content = "password=supersecret123 is the issue"
        note = await add_note(customer_id, "note", content, db_session)
        assert note is not None
        assert "supersecret123" not in note.content
        assert "[REDACTED]" in note.content

    async def test_invalid_memory_type_raises(self, db_session, customer_id) -> None:
        from memory.long_term import add_note
        with pytest.raises(ValueError, match="Unknown memory_type"):
            await add_note(customer_id, "unknown_type", "content", db_session)

    async def test_blank_content_after_scrub_returns_none(self, db_session, customer_id) -> None:
        from memory.long_term import add_note
        note = await add_note(customer_id, "note", "   ", db_session)
        assert note is None

    async def test_all_valid_types_accepted(self, db_session, customer_id) -> None:
        from memory.long_term import VALID_TYPES, add_note
        for mem_type in VALID_TYPES:
            cid = str(uuid.uuid4())
            note = await add_note(cid, mem_type, f"test {mem_type}", db_session)
            assert note is not None

    async def test_recall_respects_limit(self, db_session, customer_id) -> None:
        from memory.long_term import add_note, recall
        for i in range(5):
            await add_note(customer_id, "note", f"note {i} {uuid.uuid4()}", db_session)
        notes = await recall(customer_id, db_session, limit=3)
        assert len(notes) <= 3

    async def test_recall_default_limit_is_10(self, db_session, customer_id) -> None:
        from memory.long_term import MAX_NOTES, add_note, recall
        for i in range(MAX_NOTES + 3):
            await add_note(customer_id, "note", f"note {i} {uuid.uuid4()}", db_session)
        notes = await recall(customer_id, db_session)
        assert len(notes) <= MAX_NOTES


# ---------------------------------------------------------------------------
# memory_service tests (async, full integration)
# ---------------------------------------------------------------------------


class TestMemoryService:
    async def test_recall_empty_customer_returns_empty(self, db_session) -> None:
        from memory.memory_service import recall_customer
        notes = await recall_customer(str(uuid.uuid4()), db_session)
        assert notes == []

    async def test_recall_returns_dicts(self, db_session) -> None:
        from memory.long_term import add_note
        from memory.memory_service import recall_customer
        cid = str(uuid.uuid4())
        await add_note(cid, "note", "some note", db_session)
        notes = await recall_customer(cid, db_session)
        assert len(notes) == 1
        note = notes[0]
        assert "type" in note
        assert "content" in note
        assert "ticket_id" in note
        assert "created_at" in note

    async def test_record_resolution_writes_notes(self, db_session) -> None:
        from memory.long_term import recall
        from memory.memory_service import record_resolution
        cid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        await record_resolution(
            customer_id=cid,
            ticket_id=tid,
            subject="Cannot login",
            troubleshooting_steps=["Check SSO config", "Reset password", "Clear cache"],
            resolution_summary="SSO was misconfigured; fixed IdP settings.",
            session=db_session,
        )
        notes = await recall(cid, db_session)
        types = {n.memory_type for n in notes}
        assert "past_issue" in types
        assert "troubleshooting" in types
        assert "note" in types

    async def test_record_resolution_stores_at_most_3_steps(self, db_session) -> None:
        from memory.long_term import recall
        from memory.memory_service import record_resolution
        cid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        await record_resolution(
            customer_id=cid,
            ticket_id=tid,
            subject="Storage full",
            troubleshooting_steps=[f"step {i}" for i in range(10)],
            resolution_summary="Upgraded plan.",
            session=db_session,
        )
        notes = await recall(cid, db_session)
        troubleshooting = [n for n in notes if n.memory_type == "troubleshooting"]
        assert len(troubleshooting) <= 3

    async def test_record_resolution_idempotent(self, db_session) -> None:
        from memory.long_term import recall
        from memory.memory_service import record_resolution
        cid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        kwargs = dict(
            customer_id=cid,
            ticket_id=tid,
            subject="Duplicate test",
            troubleshooting_steps=["step A"],
            resolution_summary="Fixed it.",
            session=db_session,
        )
        await record_resolution(**kwargs)
        await record_resolution(**kwargs)
        notes = await recall(cid, db_session)
        # Duplicate writes must not double the count
        past_issues = [n for n in notes if n.memory_type == "past_issue"]
        assert len(past_issues) == 1

    async def test_record_resolution_scrubs_secrets(self, db_session) -> None:
        from memory.long_term import recall
        from memory.memory_service import record_resolution
        cid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        await record_resolution(
            customer_id=cid,
            ticket_id=tid,
            subject="API issue",
            troubleshooting_steps=["api_key=sk-ant-secret123abc"],
            resolution_summary="Rotated key.",
            session=db_session,
        )
        notes = await recall(cid, db_session)
        for note in notes:
            assert "sk-ant-" not in note.content
