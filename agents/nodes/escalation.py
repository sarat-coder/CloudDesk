"""Node: escalation — create an escalation record and update ticket status."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

NODE = "escalation"


async def escalation(state: dict) -> dict:
    from app.core.observability import tracer_for
    from app.core.database import get_session
    from app.models.entities import Escalation, Ticket
    from sqlalchemy import select

    tracer = tracer_for(state)
    errors: list[str] = []

    async with tracer.node(NODE):
        escalation_decision = state.get("escalation_decision")
        ticket_id = state.get("ticket_id", "")
        run_id = state.get("workflow_id", "")

        team = "Support Team"
        reason = "Escalated by support workflow"
        priority = state.get("severity", "medium")

        if escalation_decision:
            team = escalation_decision.team or team
            reason = escalation_decision.reason or reason

        try:
            async with get_session() as session:
                # Create escalation record
                esc = Escalation(
                    id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    run_id=run_id or None,
                    team=team,
                    reason=reason,
                    priority=priority,
                    status="open",
                    created_by="workflow",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(esc)

                # Update ticket status
                result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
                ticket = result.scalar_one_or_none()
                if ticket:
                    ticket.status = "escalated"
                    ticket.updated_at = datetime.now(timezone.utc)

                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("escalation node DB error: %s", exc)
            errors.append(f"escalation DB write failed: {exc}")

    return {
        "completed_nodes": [NODE],
        "current_node": NODE,
        "errors": errors,
    }
