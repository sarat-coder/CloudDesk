"""Workflow service — creates workflow_runs and drives the LangGraph.

§4.1 of CLAUDE.md request flow:
  1. create_run()         → writes workflow_runs row, returns workflow_id
  2. start_workflow()     → runs the graph in a background task
  3. get_latest_run()     → returns the most recent WorkflowRun for a ticket
  4. get_run_events()     → returns WorkflowEvents for a run

After every node the state is checkpointed by LangGraph automatically.
The API polls /workflow every 2 s to read updated state.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import WorkflowEvent, WorkflowRun

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# create_run — synchronous DB write, returns immediately
# ---------------------------------------------------------------------------


async def create_run(
    session: AsyncSession,
    ticket_id: str,
    started_by: str | None = None,
) -> WorkflowRun:
    """Insert a new workflow_runs row and return it."""
    run = WorkflowRun(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        status="running",
        state={},
        started_by=started_by,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


# ---------------------------------------------------------------------------
# start_workflow — runs the graph, called from BackgroundTasks
# ---------------------------------------------------------------------------


async def start_workflow(
    ticket_id: str,
    subject: str,
    body: str,
    channel: str,
    customer_id: str,
    workflow_id: str,
) -> None:
    """Run the support workflow for one ticket.

    This function is called in a FastAPI BackgroundTasks context.
    It drives the LangGraph graph with astream and updates the
    workflow_runs row on completion.
    """
    start_ts = time.monotonic()

    from agents.graph import get_graph
    from app.core.database import get_session

    graph = get_graph()
    thread_config = {"configurable": {"thread_id": workflow_id}}

    initial_state: dict[str, Any] = {
        "ticket_id": ticket_id,
        "ticket_number": "",
        "subject": subject,
        "body": body,
        "channel": channel,
        "customer_id": customer_id,
        "workflow_id": workflow_id,
        "injection_flagged": False,
        "classification": None,
        "severity": "medium",
        "severity_reason": "",
        "customer_context": None,
        "evidence": [],
        "previous_cases": [],
        "diagnosis": None,
        "resolution_plan": None,
        "planned_actions": [],
        "escalation_decision": None,
        "risk_level": "low",
        "ticket_summary": None,
        "final_response": None,
        "errors": [],
        "completed_nodes": [],
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
        "current_node": None,
    }

    final_status = "completed"
    final_state: dict[str, Any] = {}

    try:
        async for chunk in graph.astream(initial_state, config=thread_config):
            # chunk is a dict {node_name: partial_state}; persist the latest snapshot
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict):
                    final_state.update(node_output)

            # Persist state snapshot after each node
            await _save_run_state(workflow_id, final_state)

    except Exception as exc:
        logger.error("Workflow %s failed: %s", workflow_id, exc, exc_info=True)
        final_status = "failed"
        # Write an error event
        try:
            async with get_session() as session:
                event = WorkflowEvent(
                    id=str(uuid.uuid4()),
                    run_id=workflow_id,
                    event_type="error",
                    node=None,
                    data={"message": str(exc)[:1000]},
                )
                session.add(event)
                await session.commit()
        except Exception:  # noqa: BLE001
            pass

    # Determine status from final state
    completed_nodes = final_state.get("completed_nodes", [])
    if "escalation" in completed_nodes:
        final_status = "escalated"
    elif "human_approval" in completed_nodes and "execute_resolution" not in completed_nodes:
        # Paused at human_approval
        final_status = "waiting_on_approval"
    elif final_status != "failed":
        final_status = "completed"

    duration_ms = int((time.monotonic() - start_ts) * 1000)

    # Update the workflow run row
    try:
        async with get_session() as session:
            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id)
            )
            run = result.scalar_one_or_none()
            if run:
                run.status = final_status
                run.state = _serialise_state(final_state)
                run.completed_at = datetime.now(timezone.utc)
                run.updated_at = datetime.now(timezone.utc)

            # Write workflow_completed event
            event = WorkflowEvent(
                id=str(uuid.uuid4()),
                run_id=workflow_id,
                event_type="workflow_completed",
                node=None,
                data={"status": final_status, "duration_ms": duration_ms},
            )
            session.add(event)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to finalise workflow run %s: %s", workflow_id, exc)


async def _save_run_state(workflow_id: str, state: dict[str, Any]) -> None:
    """Persist a snapshot of the workflow state after each node."""
    try:
        from app.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id)
            )
            run = result.scalar_one_or_none()
            if run:
                run.state = _serialise_state(state)
                run.updated_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception:  # noqa: BLE001
        pass  # State snapshot is best-effort


def _serialise_state(state: dict[str, Any]) -> dict[str, Any]:
    """Convert state to a JSON-serialisable dict (Pydantic models → dicts)."""
    out: dict[str, Any] = {}
    for k, v in state.items():
        if hasattr(v, "model_dump"):
            out[k] = v.model_dump()
        elif isinstance(v, list):
            out[k] = [
                item.model_dump() if hasattr(item, "model_dump") else item for item in v
            ]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Query helpers — read workflow state from DB
# ---------------------------------------------------------------------------


async def get_latest_run(
    session: AsyncSession,
    ticket_id: str,
) -> WorkflowRun | None:
    """Return the most recent workflow run for a ticket."""
    result = await session.execute(
        select(WorkflowRun)
        .where(WorkflowRun.ticket_id == ticket_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_run(session: AsyncSession, run_id: str) -> WorkflowRun | None:
    result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    return result.scalar_one_or_none()


async def get_run_events(
    session: AsyncSession,
    run_id: str,
) -> list[WorkflowEvent]:
    """Return all events for a workflow run, ordered by creation time."""
    result = await session.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.run_id == run_id)
        .order_by(WorkflowEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def get_active_run(
    session: AsyncSession,
    ticket_id: str,
) -> WorkflowRun | None:
    """Return a running or waiting_on_approval workflow run for a ticket."""
    result = await session.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.ticket_id == ticket_id,
            WorkflowRun.status.in_(["running", "waiting_on_approval"]),
        )
        .order_by(WorkflowRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
