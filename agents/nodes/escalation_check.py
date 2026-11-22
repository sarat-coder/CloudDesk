"""Node: escalation_check — run EscalationAgent to decide if escalation is needed."""
from __future__ import annotations

from app.core.observability import record_llm, record_tool_calls, tracer_for

NODE = "escalation_check"


async def escalation_check(state: dict) -> dict:
    from agents.specialists.escalation import EscalationAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        agent = EscalationAgent()
        decision, usage, ms, calls = await agent.run(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
            severity=state.get("severity", "medium"),
            resolution_plan=state.get("resolution_plan"),
        )
        await record_tool_calls(tracer, NODE, calls)
        if usage.get("total_tokens", 0) > 0:
            await record_llm(tracer, NODE, usage, ms, "escalation_decision")

    return {
        "escalation_decision": decision,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
