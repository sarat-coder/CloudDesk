"""Long-term customer memory backed by the customer_memory table.

Memory types (§7.5 CLAUDE.md):
  preference      — stored user/account preferences observed from tickets
  past_issue      — a previous problem and how it was resolved
  troubleshooting — a troubleshooting step that worked for this customer
  note            — general agent note about the customer

Rules (all enforced here):
  - Every note is passed through scrub() before writing (N7).
  - Exact-duplicate notes (same customer + type + content) are silently skipped.
  - Never store: card numbers, API keys, passwords, raw ticket bodies,
    or anything about other customers.
  - Recall returns at most MAX_NOTES (10) notes per customer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.guardrails import scrub
from app.models.entities import CustomerMemory

MAX_NOTES = 10

VALID_TYPES = frozenset({"preference", "past_issue", "troubleshooting", "note"})


async def recall(
    customer_id: str,
    session: AsyncSession,
    limit: int = MAX_NOTES,
) -> list[CustomerMemory]:
    """Return the most recent *limit* memory notes for a customer."""
    result = await session.execute(
        select(CustomerMemory)
        .where(CustomerMemory.customer_id == customer_id)
        .order_by(CustomerMemory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def add_note(
    customer_id: str,
    memory_type: str,
    content: str,
    session: AsyncSession,
    ticket_id: str | None = None,
) -> CustomerMemory | None:
    """Write one memory note, skipping exact duplicates and scrubbing secrets.

    Returns the new CustomerMemory row, or None when skipped as a duplicate.
    """
    if memory_type not in VALID_TYPES:
        raise ValueError(f"Unknown memory_type {memory_type!r}. Must be one of {VALID_TYPES}.")

    clean = scrub(content).strip()
    if not clean:
        return None

    # Duplicate check: same customer + same type + same scrubbed content
    existing = await session.execute(
        select(CustomerMemory.id).where(
            CustomerMemory.customer_id == customer_id,
            CustomerMemory.memory_type == memory_type,
            CustomerMemory.content == clean,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None

    note = CustomerMemory(
        id=str(uuid.uuid4()),
        customer_id=customer_id,
        memory_type=memory_type,
        content=clean,
        ticket_id=ticket_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(note)
    await session.flush()
    await session.refresh(note)
    return note
