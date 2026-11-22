"""Node: ticket_summary — generate a one-paragraph internal summary."""
from __future__ import annotations

from app.core.observability import record_llm, tracer_for

NODE = "ticket_summary"


async def ticket_summary(state: dict) -> dict:
    from agents.specialists.supervisor import SupervisorAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        agent = SupervisorAgent()
        resolution_plan = state.get("resolution_plan")
        summary_text, usage, ms, _ = await agent.summarize_ticket(
            subject=state.get("subject", ""),
            resolution_summary=resolution_plan.summary if resolution_plan else "",
            internal_notes=resolution_plan.internal_notes if resolution_plan else "",
        )
        await record_llm(tracer, NODE, usage, ms, "ticket_summary")

    return {
        "ticket_summary": summary_text,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
