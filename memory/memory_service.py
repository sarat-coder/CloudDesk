"""Memory service — the single entry point agents use for memory operations.

Agents MUST call only these two functions, never long_term / short_term directly:

  recall_customer(customer_id, session)
      → list[dict]  (up to 10 notes, ready to inject into a prompt)

  record_resolution(customer_id, ticket_id, subject, troubleshooting_steps,
                    resolution_summary, session)
      → None  (writes past_issue + troubleshooting + note; skips duplicates)

§7.5 of CLAUDE.md.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from memory import long_term

# Maximum number of troubleshooting steps to store per resolution.
_MAX_STEPS = 3


async def recall_customer(
    customer_id: str,
    session: AsyncSession,
) -> list[dict[str, str]]:
    """Return up to 10 memory notes for a customer as plain dicts.

    Each dict has keys: type, content, ticket_id, created_at.
    """
    notes = await long_term.recall(customer_id, session)
    return [
        {
            "type": n.memory_type,
            "content": n.content,
            "ticket_id": n.ticket_id or "",
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in notes
    ]


async def record_resolution(
    customer_id: str,
    ticket_id: str,
    subject: str,
    troubleshooting_steps: list[str],
    resolution_summary: str,
    session: AsyncSession,
) -> None:
    """Persist memory notes after a ticket is resolved.

    Writes (skipping duplicates):
      1. past_issue   — "{subject}: {resolution_summary}"
      2. troubleshooting — first up to 3 steps, one note each
      3. note         — the resolution_summary on its own as a free note
    """
    # 1. Record what the problem was and how it was resolved.
    if subject and resolution_summary:
        past_issue_content = f"{subject}: {resolution_summary}"
        await long_term.add_note(
            customer_id=customer_id,
            memory_type="past_issue",
            content=past_issue_content,
            session=session,
            ticket_id=ticket_id,
        )

    # 2. Record the first N troubleshooting steps that worked.
    for step in troubleshooting_steps[:_MAX_STEPS]:
        if step and step.strip():
            await long_term.add_note(
                customer_id=customer_id,
                memory_type="troubleshooting",
                content=step.strip(),
                session=session,
                ticket_id=ticket_id,
            )

    # 3. Store the resolution summary as a free note.
    if resolution_summary and resolution_summary.strip():
        await long_term.add_note(
            customer_id=customer_id,
            memory_type="note",
            content=resolution_summary.strip(),
            session=session,
            ticket_id=ticket_id,
        )
