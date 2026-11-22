"""Node: classify_severity — assess ticket severity with rules-first pattern."""
from __future__ import annotations

from app.core.observability import record_llm, record_tool_calls, tracer_for

NODE = "classify_severity"


async def classify_severity(state: dict) -> dict:
    from agents.specialists.supervisor import SupervisorAgent

    tracer = tracer_for(state)
    async with tracer.node(NODE):
        agent = SupervisorAgent()
        assessment, usage, ms, calls = await agent.assess_severity(
            subject=state.get("subject", ""),
            body=state.get("body", ""),
        )
        await record_tool_calls(tracer, NODE, calls)
        await record_llm(tracer, NODE, usage, ms, "severity_assessment")

    return {
        "severity": assessment.severity.value if hasattr(assessment.severity, "value") else str(assessment.severity),
        "severity_reason": assessment.reason,
        "token_usage": usage,
        "completed_nodes": [NODE],
        "current_node": NODE,
    }
