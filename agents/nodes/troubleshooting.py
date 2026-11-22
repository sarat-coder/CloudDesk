"""Node: troubleshooting — diagnose the problem with playbooks and service status."""
from __future__ import annotations

from app.core.observability import record_llm, record_tool_calls, tracer_for

NODE = "troubleshooting"


async def troubleshooting(state: dict) -> dict:
    from agents.specialists.troubleshooting import TroubleshootingAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        classification = state.get("classification")
        category = ""
        if classification:
            cat = classification.category
            category = cat.value if hasattr(cat, "value") else str(cat)

        agent = TroubleshootingAgent()
        diagnosis, usage, ms, calls = await agent.run(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
            category=category,
            evidence=state.get("evidence", []),
        )
        await record_tool_calls(tracer, NODE, calls)
        await record_llm(tracer, NODE, usage, ms, "diagnosis")

    return {
        "diagnosis": diagnosis,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
