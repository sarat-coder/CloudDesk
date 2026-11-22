"""Node: understand_ticket — classifies the ticket and scans for injection."""
from __future__ import annotations

from app.core.observability import record_llm, record_tool_calls, tracer_for

NODE = "understand_ticket"


async def understand_ticket(state: dict) -> dict:
    from agents.specialists.supervisor import SupervisorAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        agent = SupervisorAgent()
        classification, injection_flagged, usage, ms, calls = await agent.understand_ticket(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
        )
        await record_tool_calls(tracer, NODE, calls)
        if usage.get("total_tokens", 0) > 0:
            await record_llm(tracer, NODE, usage, ms, "classification")

    return {
        "classification": classification,
        "injection_flagged": injection_flagged,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
