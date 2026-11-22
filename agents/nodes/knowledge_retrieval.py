"""Node: knowledge_retrieval — retrieve KB articles and find similar cases."""
from __future__ import annotations

from app.core.observability import record_tool_calls, tracer_for

NODE = "knowledge_retrieval"


async def knowledge_retrieval(state: dict) -> dict:
    from agents.specialists.knowledge import KnowledgeAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        classification = state.get("classification")
        category = ""
        if classification:
            cat = classification.category
            category = cat.value if hasattr(cat, "value") else str(cat)

        # Extract ticket history from customer context if available
        customer_ctx = state.get("customer_context")
        ticket_history = customer_ctx.ticket_history if customer_ctx else []

        agent = KnowledgeAgent()
        evidence, previous_cases, usage, ms, calls = await agent.run(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
            category=category,
            ticket_history=ticket_history,
        )
        await record_tool_calls(tracer, NODE, calls)

    return {
        "evidence": evidence,
        "previous_cases": previous_cases,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
