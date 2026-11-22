"""Node: resolution_planning — build the resolution plan and determine actions."""
from __future__ import annotations

from app.core.observability import record_llm, record_tool_calls, tracer_for

NODE = "resolution_planning"


async def resolution_planning(state: dict) -> dict:
    from agents.specialists.resolution import ResolutionAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        classification = state.get("classification")
        category = ""
        if classification:
            cat = classification.category
            category = cat.value if hasattr(cat, "value") else str(cat)

        agent = ResolutionAgent()
        plan, planned_actions, output_valid, usage, ms, calls = await agent.run(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
            category=category,
            severity=state.get("severity", "medium"),
            customer_context=state.get("customer_context"),
            evidence=state.get("evidence", []),
            diagnosis=state.get("diagnosis"),
            ticket_id=state.get("ticket_id", ""),
        )
        await record_tool_calls(tracer, NODE, calls)
        await record_llm(tracer, NODE, usage, ms, "resolution_plan")

    errors: list[str] = []
    if not output_valid:
        errors.append("Output validation failed — customer reply replaced with safe fallback")

    return {
        "resolution_plan": plan,
        "planned_actions": planned_actions,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
        "errors": errors,
    }
