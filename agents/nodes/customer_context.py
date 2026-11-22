"""Node: customer_context — load customer data, subscription, history, memory."""
from __future__ import annotations

from app.core.observability import record_tool_calls, tracer_for

NODE = "customer_context"


async def customer_context(state: dict) -> dict:
    from agents.specialists.customer import CustomerAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        agent = CustomerAgent()
        context, usage, ms, calls = await agent.run(
            customer_id=state.get("customer_id", ""),
            ticket_id=state.get("ticket_id", ""),
        )
        await record_tool_calls(tracer, NODE, calls)

    return {
        "customer_context": context,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
