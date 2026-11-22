"""Approval service — decide on a pending approval and resume the workflow.

§4.1 steps 7-8:
  POST /approvals/{id}/approve → approval_service.decide()
                               → resume_workflow(Command(resume={...}))
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ApprovalRequest, Ticket, WorkflowRun

logger = logging.getLogger(__name__)


async def get_pending_approval(
    session: AsyncSession,
    approval_id: str,
) -> ApprovalRequest | None:
    result = await session.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    return result.scalar_one_or_none()


async def decide(
    session: AsyncSession,
    approval_id: str,
    approved: bool,
    decided_by: str,
) -> dict:
    """Record the decision and resume the paused workflow.

    Returns a dict with the approval status and run_id.
    Raises ValueError for invalid states.
    """
    approval = await get_pending_approval(session, approval_id)
    if approval is None:
        raise ValueError(f"Approval {approval_id!r} not found")
    if approval.status != "pending":
        raise ValueError(f"Approval {approval_id!r} is already {approval.status}")

    # Update approval record
    approval.status = "approved" if approved else "rejected"
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    approval.updated_at = datetime.now(timezone.utc)
    await session.commit()

    # Resume the paused LangGraph workflow
    run_id = approval.run_id
    try:
        await resume_workflow(
            run_id=run_id,
            approved=approved,
            decided_by=decided_by,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to resume workflow %s after approval decision: %s",
            run_id,
            exc,
            exc_info=True,
        )
        raise

    return {
        "approval_id": approval_id,
        "run_id": run_id,
        "decision": "approved" if approved else "rejected",
        "decided_by": decided_by,
    }


async def resume_workflow(
    run_id: str,
    approved: bool,
    decided_by: str,
) -> None:
    """Resume a paused LangGraph workflow with the approval decision.

    The graph was interrupted at the human_approval node.
    We pass a Command(resume={...}) to continue.
    """
    from langgraph.types import Command

    from agents.graph import get_graph
    from app.core.database import get_session
    from app.services.workflow_service import _serialise_state

    graph = get_graph()
    thread_config = {"configurable": {"thread_id": run_id}}

    resume_value = {"approved": approved, "decided_by": decided_by}

    final_state: dict = {}
    final_status = "completed"

    try:
        async for chunk in graph.astream(
            Command(resume=resume_value),
            config=thread_config,
        ):
            for _node, node_output in chunk.items():
                if isinstance(node_output, dict):
                    final_state.update(node_output)

    except Exception as exc:
        logger.error("resume_workflow %s failed: %s", run_id, exc, exc_info=True)
        final_status = "failed"

    completed_nodes = final_state.get("completed_nodes", [])
    if "escalation" in completed_nodes:
        final_status = "escalated"
    elif final_status != "failed":
        final_status = "completed"

    # Persist final state
    try:
        async with get_session() as session:
            result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = final_status
                run.state = _serialise_state(final_state)
                run.completed_at = datetime.now(timezone.utc)
                run.updated_at = datetime.now(timezone.utc)

            # Also update the ticket status
            if final_state.get("ticket_id"):
                t_result = await session.execute(
                    select(Ticket).where(Ticket.id == final_state["ticket_id"])
                )
                ticket = t_result.scalar_one_or_none()
                if ticket and ticket.status == "waiting_on_approval":
                    ticket.status = "in_progress" if final_status == "completed" else "escalated"
                    ticket.updated_at = datetime.now(timezone.utc)

            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to persist resumed workflow %s: %s", run_id, exc)
