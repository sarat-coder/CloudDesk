"""Node: human_approval — pause the graph until a human approves or rejects.

Code *before* interrupt() is idempotent — it may re-run on resume.
The interrupt() call suspends the graph; the state is checkpointed so it can
be resumed with Command(resume=...).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from langgraph.types import interrupt

logger = logging.getLogger(__name__)

NODE = "human_approval"


async def human_approval(state: dict) -> dict:
    from app.core.database import get_session
    from app.core.observability import tracer_for
    from app.models.entities import ApprovalRequest, Ticket
    from sqlalchemy import select

    tracer = tracer_for(state)
    ticket_id = state.get("ticket_id", "")
    run_id = state.get("workflow_id", "")
    planned_actions = state.get("planned_actions", [])

    # Idempotent: create the approval_requests row (if not already there)
    approval_id = ""
    try:
        async with get_session() as session:
            # Check if there's already a pending approval for this run
            result = await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.run_id == run_id,
                    ApprovalRequest.status == "pending",
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                approval_id = existing.id
            else:
                approval_id = str(uuid.uuid4())
                reason = "; ".join(
                    a.description for a in planned_actions if a.requires_approval
                ) or "Human approval required"
                approval = ApprovalRequest(
                    id=approval_id,
                    run_id=run_id,
                    ticket_id=ticket_id,
                    status="pending",
                    reason=reason,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(approval)

                # Update ticket status
                t_result = await session.execute(select(Ticket).where(Ticket.id == ticket_id))
                ticket = t_result.scalar_one_or_none()
                if ticket:
                    ticket.status = "waiting_on_approval"
                    ticket.updated_at = datetime.now(timezone.utc)

                await session.commit()

            await tracer.approval_requested(
                node=NODE,
                approval_id=approval_id,
                reason="Awaiting human approval for consequential actions",
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("human_approval DB setup error: %s", exc)

    # Suspend the graph — control returns here on resume with the decision
    decision = interrupt({"approval_id": approval_id, "run_id": run_id})

    # --- resumed ---
    approved = decision.get("approved", False) if isinstance(decision, dict) else False
    decided_by = decision.get("decided_by", "unknown") if isinstance(decision, dict) else "unknown"

    try:
        async with get_session() as session:
            await tracer.approval_resolved(
                node=NODE,
                approval_id=approval_id,
                decision="approved" if approved else "rejected",
                decided_by=decided_by,
            )
    except Exception:  # noqa: BLE001
        pass

    return {
        "completed_nodes": [NODE],
        "current_node": NODE,
        "_approval_decision": approved,
        "_decided_by": decided_by,
    }
