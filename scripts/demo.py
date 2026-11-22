"""Demo script — runs a ticket through the CloudDesk workflow end-to-end.

Usage:
  python scripts/demo.py [TICKET_NUMBER]

Defaults to CD-1002 (refund — pauses for approval).
CD-1005 escalates by rule.
"""
from __future__ import annotations

import asyncio
import sys


async def main(ticket_number: str = "CD-1002") -> None:
    # Boot the app environment
    import os
    os.environ.setdefault("DEMO_MODE", "true")
    os.environ.setdefault("LLM_PROVIDER", "fake")
    os.environ.setdefault("VECTOR_STORE", "memory")
    os.environ.setdefault("USE_FAKE_REDIS", "true")
    os.environ.setdefault("JWT_SECRET", "demo-secret")
    os.environ.setdefault("CHECKPOINT_DB_PATH", ":memory:")

    from app.core.database import create_tables
    from app.core.config import get_settings
    from app.services.seed_service import bootstrap_demo_data

    await create_tables()
    await bootstrap_demo_data()

    # Ingest knowledge base
    try:
        from rag.ingest import run_ingest
        settings = get_settings()
        await run_ingest(settings)
    except Exception as e:
        print(f"[warn] Knowledge ingest skipped: {e}")

    # Find the ticket
    from app.core.database import get_session
    from sqlalchemy import select
    from app.models.entities import Ticket

    async with get_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_number == ticket_number)
        )
        ticket = result.scalar_one_or_none()

    if ticket is None:
        print(f"[error] Ticket {ticket_number!r} not found in demo DB")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Demo: Running workflow for {ticket_number}")
    print(f"Subject: {ticket.subject}")
    print(f"{'='*60}\n")

    # Build graph with in-memory checkpointer
    from agents.checkpointer import get_checkpointer
    from agents.graph import build_graph, reset_graph

    reset_graph()
    checkpointer = get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)

    import uuid
    workflow_id = str(uuid.uuid4())
    thread_config = {"configurable": {"thread_id": workflow_id}}

    initial_state = {
        "ticket_id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "subject": ticket.subject,
        "body": ticket.body,
        "channel": ticket.channel,
        "customer_id": ticket.customer_id,
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
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
        "current_node": None,
    }

    final_state = {}
    interrupted = False

    print("Running workflow nodes...")
    async for chunk in graph.astream(initial_state, config=thread_config):
        for node_name, node_output in chunk.items():
            if node_name == "__interrupt__":
                print(f"\n>>> PAUSED at human_approval (approval required)")
                print(f"    Approval data: {node_output}")
                interrupted = True
                break
            elif isinstance(node_output, dict):
                completed = node_output.get("completed_nodes", [])
                if completed:
                    print(f"  ✓ {completed[-1]}")
                final_state.update(node_output)
        if interrupted:
            break

    if interrupted:
        # Ask for approval
        print("\n" + "="*60)
        print("AWAITING HUMAN APPROVAL")
        print("Planned actions require approval before execution.")

        answer = input("\nApprove actions? [Y/n]: ").strip().lower()
        approved = answer not in ("n", "no")

        print(f"\n{'Approved' if approved else 'Rejected'} — resuming workflow...\n")

        from langgraph.types import Command

        async for chunk in graph.astream(
            Command(resume={"approved": approved, "decided_by": "demo-user"}),
            config=thread_config,
        ):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict):
                    completed = node_output.get("completed_nodes", [])
                    if completed:
                        print(f"  ✓ {completed[-1]}")
                    final_state.update(node_output)

    print(f"\n{'='*60}")
    print("WORKFLOW COMPLETE")
    print(f"Risk level: {final_state.get('risk_level', 'unknown')}")
    print(f"Completed nodes: {', '.join(final_state.get('completed_nodes', []))}")

    resolution_plan = final_state.get("resolution_plan")
    if resolution_plan:
        summary = resolution_plan.summary if hasattr(resolution_plan, "summary") else resolution_plan.get("summary", "")
        reply = resolution_plan.customer_reply if hasattr(resolution_plan, "customer_reply") else resolution_plan.get("customer_reply", "")
        print(f"\nSummary: {summary}")
        print(f"\nCustomer reply:\n{reply}")

    escalation_decision = final_state.get("escalation_decision")
    if escalation_decision:
        required = escalation_decision.escalation_required if hasattr(escalation_decision, "escalation_required") else escalation_decision.get("escalation_required", False)
        team = escalation_decision.team if hasattr(escalation_decision, "team") else escalation_decision.get("team")
        if required:
            print(f"\n⚠ ESCALATED to: {team}")

    errors = final_state.get("errors", [])
    if errors:
        print(f"\nErrors: {errors}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    ticket_number = sys.argv[1] if len(sys.argv) > 1 else "CD-1002"
    asyncio.run(main(ticket_number))
